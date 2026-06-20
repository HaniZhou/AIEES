"""认证相关接口"""

from datetime import timedelta

from app.core.exceptions import AppBusinessException
from app.common.response import response_success
from app.core.config import SecretConfig
from app.core.logging import get_logger
from app.core.rate_limiter import (
    check_login_status,
    clear_login_failures,
    record_login_failure,
    store_captcha,
    verify_captcha,
)
from app.core.redis import get_redis
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_token_return_payload,
)
from app.schema.user import (
    UserLogin,
    UserUpdatePassword,
)
from app.service.auth_service import AuthService
from app.util.captcha_util import generate_math_captcha
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter()
auth_route_logger = get_logger(__name__)


@router.get("/captcha")
async def get_captcha():
    redis_client = get_redis()
    captcha_data = generate_math_captcha()

    await store_captcha(
        redis_client,
        captcha_data["captcha_key"],
        captcha_data["_answer"],
    )

    return response_success(
        {
            "captcha_key": captcha_data["captcha_key"],
            "captcha_image": captcha_data["captcha_image"],
        }
    )


@router.post("/token")
async def login_for_access_token(
    login_form: UserLogin,
    auth_svc: AuthService = Depends(AuthService),
):
    redis_client = get_redis()
    user_id = login_form.id

    status_info = await check_login_status(redis_client, user_id)

    if status_info["status"] == "locked":
        remain_min = (status_info["lock_ttl"] or 900) // 60
        raise AppBusinessException(
            423,
            f"账号已被锁定，请 {remain_min} 分钟后重试",
            data={"locked": True, "lock_ttl": status_info["lock_ttl"]},
        )

    if status_info["status"] == "need_captcha":
        if not login_form.captcha_key or not login_form.captcha_code:
            raise AppBusinessException(
                403,
                "登录失败次数过多，请获取验证码后重试",
                data={"need_captcha": True, "fail_count": status_info["fail_count"]},
            )
        if not await verify_captcha(redis_client, login_form.captcha_key, login_form.captcha_code):
            raise AppBusinessException(
                400,
                "验证码错误或已过期",
                data={},
            )

    user = await auth_svc.authenticate_user(login_form.id, login_form.password, login_form.role)

    if not user:
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
        raise AppBusinessException(401, "登录失败，用户名或密码错误", data=response_data)

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
        return response_success(
            {
                "access_token": access_token,
                "token_type": "bearer",
                "user": user.model_dump(mode="json"),
            }
        )
    except Exception as e:
        auth_route_logger.error(f"Token generation failed for user [{user_id}]: {str(e)}")
        raise


@router.post("/password")
async def update_password(
    password_form: UserUpdatePassword,
    token_data=Depends(verify_token_return_payload),
    auth_svc: AuthService = Depends(AuthService),
):
    user_id = token_data.id
    user_role = token_data.role

    verified_user = await auth_svc.authenticate_user(user_id, password_form.old_password, user_role)

    if not verified_user:
        auth_route_logger.warning(f"Password change failed for user [{user_id}]: wrong old password")
        raise AppBusinessException(400, "原密码输入错误")

    try:
        new_hashed_password = get_password_hash(password_form.new_password)
        success = await auth_svc.update_password(verified_user.id, verified_user.role, new_hashed_password)

        if success:
            auth_route_logger.info(f"Password updated successfully for user [{user_id}]")
            return response_success(data={})
        else:
            raise AppBusinessException(500, "更新失败，请稍后重试")
    except Exception as e:
        auth_route_logger.error(f"DB error updating password for user [{user_id}]: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误") from e
