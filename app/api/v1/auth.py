"""认证相关接口"""
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import (
    authenticate_user,
    verify_token_return_payload,
    get_password_hash, create_access_token,
)
from app.core.rate_limiter import (
    check_login_status,
    verify_captcha,
    record_login_failure,
    clear_login_failures,
    store_captcha,
)
from app.core.captcha import generate_math_captcha
from app.core.redis_pool import get_redis
from app.model.schema.schema import (
    UserLogin,
    UserUpdatePassword,  # 新增导入：修改密码的请求模型
)
from app.crud.db import db_update_user  # 新增导入：数据库更新函数
from app.Config import SecretConfig
from app.core.response import _success, _error, _created

router = APIRouter()
auth_route_logger = logging.getLogger("auth.route")

#  验证码接口 


@router.get("/captcha")
async def get_captcha():
    """
    函数目的：生成一道数学计算验证题，返回 captcha_key 和 base64 图片。
    参数信息：无。
    返回值：统一响应，data 包含 captcha_key 和 captcha_image。
    """
    redis_client = get_redis()
    captcha_data = generate_math_captcha()

    # 将答案存入 Redis，TTL 300 秒
    await store_captcha(
        redis_client,
        captcha_data["captcha_key"],
        captcha_data["_answer"],
    )

    return _success({
        "captcha_key": captcha_data["captcha_key"],
        "captcha_image": captcha_data["captcha_image"],
    })


#  登录接口（含限流 + 验证码联动） 


@router.post("/token")
async def login_for_access_token(login_form: UserLogin):
    """
    函数目的：处理登录请求。执行顺序：
             1. 检查账号锁定状态
             2. 检查是否需要验证码（连续失败 >= 3 次），需要则校验
             3. 验证用户凭据
             4. 失败则记录次数并判断是否锁定
             5. 成功则清除失败计数，签发 JWT
    参数信息：- login_form: UserLogin, 登录表单（含可选 captcha_key / captcha_code）。
    返回值：包含 token 和用户信息的统一响应。
    """
    redis_client = get_redis()
    user_id = login_form.id

    # ---- 检查账号状态 ----
    status_info = await check_login_status(redis_client, user_id)

    if status_info["status"] == "locked":
        remain_min = (status_info["lock_ttl"] or 900) // 60
        return _error(
            423,
            f"账号已被锁定，请 {remain_min} 分钟后重试",
            data={"locked": True, "lock_ttl": status_info["lock_ttl"]},
        )

    if status_info["status"] == "need_captcha":
        # 强制要求携带验证码
        if not login_form.captcha_key or not login_form.captcha_code:
            return _error(
                403,
                "登录失败次数过多，请获取验证码后重试",
                data={"need_captcha": True, "fail_count": status_info["fail_count"]},
            )
        # 校验验证码
        if not await verify_captcha(redis_client, login_form.captcha_key, login_form.captcha_code):
            return _error(
                400,
                "验证码错误或已过期",
                data={},
            )

    # ----  验证用户凭据 ----
    user = await authenticate_user(login_form.id, login_form.password, login_form.role)

    if not user:
        # 记录失败 + 判断是否触发锁定
        failure_info = await record_login_failure(redis_client, user_id)
        response_data = {}
        if failure_info["status"] in ("need_captcha", "locked"):
            response_data["need_captcha"] = True
        if failure_info["status"] == "locked":
            response_data["locked"] = True
        auth_route_logger.warning(
            f"Login rejected for user [{user_id}], "
            f"fail_count={failure_info['fail_count']}, "
            f"status={failure_info['status']}"
        )
        return _error(401, "登录失败，用户名或密码错误", data=response_data)

    # ---- 登录成功，清除失败计数，签发 Token ----
    await clear_login_failures(redis_client, user_id)

    try:
        access_token_expires = timedelta(minutes=SecretConfig.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload_data = {"id": user.id, "role": user.role}
        if user.phase:
            payload_data["phase"] = user.phase.value
        access_token = create_access_token(
            payload=payload_data,
            expires_delta=access_token_expires,
        )
        auth_route_logger.info(f"User [{user_id}] (role={user.role.value}) login succeeded")
        return _success({
            "access_token": access_token,
            "token_type": "bearer",
            "user": user.model_dump(mode="json"),
        })
    except Exception as e:
        auth_route_logger.error(f"Token generation failed for user [{user_id}]: {str(e)}")
        raise


@router.post("/password")
async def update_password(
        password_form: UserUpdatePassword,
        token_data= Depends(verify_token_return_payload)  # 注入当前登录用户信息
):
    """
    函数目的：处理已登录用户的修改密码请求。
    参数信息：
      - password_form: UserUpdatePassword, 包含旧密码和新密码。
      - token_data: TokenData, 从 JWT 中解析出的当前用户 ID 和 Role。
    返回值：统一响应格式。
    """
    user_id = token_data.id
    user_role = token_data.role

    #  验证原密码是否正确
    verified_user = await authenticate_user(user_id, password_form.old_password, user_role)

    if not verified_user:
        # 原密码错误
        auth_route_logger.warning(f"Password change failed for user [{user_id}]: wrong old password")
        return _error(400, "原密码输入错误")

    # 生成新密码哈希并更新数据库
    try:
        new_hashed_password = get_password_hash(password_form.new_password)
        success = await db_update_user(verified_user, new_hashed_password)

        if success:
            auth_route_logger.info(f"Password updated successfully for user [{user_id}]")
            return _success(data={})
        else:
            return _error(500, "更新失败，请稍后重试")
    except Exception as e:
        auth_route_logger.error(f"DB error updating password for user [{user_id}]: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误"
        )
