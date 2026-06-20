"""
登录限流与账号锁定模块
"""
from typing import Annotated

from app.core.config import AuthSecurityConfig
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.core.security import verify_token_return_payload
from app.schema.user import TokenData
from fastapi import Depends, HTTPException, Request

logger = get_logger(__name__)

#  Redis Key
CAPTCHA_KEY_PREFIX = "auth:captcha:"
LOGIN_FAIL_PREFIX = "auth:login_fail:"
LOGIN_LOCK_PREFIX = "auth:login_lock:"


def _captcha_key(captcha_key: str) -> str:
    """生成验证码 Redis Key"""
    return f"{CAPTCHA_KEY_PREFIX}{captcha_key}"


def _fail_count_key(user_id: str) -> str:
    """生成失败计数 Redis Key"""
    return f"{LOGIN_FAIL_PREFIX}{user_id}"


def _lock_key(user_id: str) -> str:
    """生成账号锁定 Redis Key"""
    return f"{LOGIN_LOCK_PREFIX}{user_id}"


async def check_login_status(redis_client, user_id: str) -> dict:
    """
    函数目的：检查账号当前登录状态（正常 / 需要验证码 / 已锁定）。
    参数信息：
        - redis_client: redis.asyncio.Redis 异步客户端实例。
        - user_id: str，待检查的用户 ID。
    返回值：dict，结构如下：
        - status: "normal" | "need_captcha" | "locked"
        - fail_count: int，当前失败次数
        - lock_ttl: int | None，剩余锁定秒数（仅 locked 状态有值）
    """
    #  检查是否被锁定
    lk = _lock_key(user_id)
    is_locked = await redis_client.exists(lk)
    if is_locked:
        ttl = await redis_client.ttl(lk)
        logger.warning(
            f"User [{user_id}] login attempt rejected: account LOCKED, "
            f"remaining {ttl}s"
        )
        return {
            "status": "locked",
            "fail_count": AuthSecurityConfig.FAIL_THRESHOLD_LOCK,
            "lock_ttl": ttl,
        }

    #  检查失败计数
    fk = _fail_count_key(user_id)
    fail_count_str = await redis_client.get(fk)
    fail_count = int(fail_count_str) if fail_count_str else 0

    if fail_count >= AuthSecurityConfig.FAIL_THRESHOLD_CAPTCHA:
        return {
            "status": "need_captcha",
            "fail_count": fail_count,
            "lock_ttl": None,
        }

    return {
        "status": "normal",
        "fail_count": fail_count,
        "lock_ttl": None,
    }


async def record_login_failure(redis_client, user_id: str) -> dict:
    """
    函数目的：记录一次登录失败，并根据累计失败次数决定是否触发锁定。
    参数信息：
        - redis_client: redis.asyncio.Redis 异步客户端实例。
        - user_id: str，登录失败的用户 ID。
    返回值：dict，包含 status（"normal"/"need_captcha"/"locked"）和 fail_count（int）。
    """
    fk = _fail_count_key(user_id)
    fail_count = await redis_client.incr(fk)

    # 首次失败时设置过期时间
    if fail_count == 1:
        await redis_client.expire(fk, AuthSecurityConfig.LOGIN_FAIL_COUNT_TTL)

    # 达到锁定阈值
    if fail_count >= AuthSecurityConfig.FAIL_THRESHOLD_LOCK:
        lk = _lock_key(user_id)
        await redis_client.set(lk, "1", ex=AuthSecurityConfig.LOGIN_LOCK_TTL)
        logger.error(
            f"User [{user_id}] account LOCKED due to "
            f"{fail_count} consecutive login failures within {AuthSecurityConfig.LOGIN_FAIL_COUNT_TTL}s"
        )
        return {"status": "locked", "fail_count": fail_count}

    logger.warning(
        f"User [{user_id}] login failed "
        f"(count: {fail_count}/{AuthSecurityConfig.FAIL_THRESHOLD_LOCK})"
    )

    return {
        "status": "need_captcha" if fail_count >= AuthSecurityConfig.FAIL_THRESHOLD_CAPTCHA else "normal",
        "fail_count": fail_count,
    }


async def clear_login_failures(redis_client, user_id: str) -> None:
    """
    函数目的：登录成功后清除该用户的失败计数记录。
    参数信息：
        - redis_client: redis.asyncio.Redis 异步客户端实例。
        - user_id: str，用户 ID。
    """
    fk = _fail_count_key(user_id)
    await redis_client.delete(fk)
    logger.info(f"User [{user_id}] login succeeded, failure count cleared")


async def store_captcha(redis_client, captcha_key: str, answer: int) -> None:
    """
    函数目的：将验证码正确答案存入 Redis，设置过期时间。
    参数信息：
        - redis_client: redis.asyncio.Redis 异步客户端实例。
        - captcha_key: str，验证码唯一标识。
        - answer: int，正确答案。
    """
    key = _captcha_key(captcha_key)
    await redis_client.set(key, str(answer), ex=AuthSecurityConfig.CAPTCHA_TTL)


async def verify_captcha(redis_client, captcha_key: str, user_answer: str) -> bool:
    """
    函数目的：验证用户提交的验证码答案是否正确，验证后立即删除 Key 防止重放。
    参数信息：
        - redis_client: redis.asyncio.Redis 异步客户端实例。
        - captcha_key: str，验证码唯一标识。
        - user_answer: str，用户提交的答案（字符串形式）。
    返回值：bool，验证是否通过。
    """
    key = _captcha_key(captcha_key)
    stored_answer = await redis_client.get(key)

    # 无论验证是否通过，立即删除
    await redis_client.delete(key)

    if not stored_answer:
        logger.warning(f"Captcha verification failed: key [{captcha_key}] not found or expired")
        return False

    # 忽略大小写比较
    is_correct = stored_answer.strip().lower() == user_answer.strip().lower()
    if not is_correct:
        logger.warning(f"Captcha verification failed for key [{captcha_key}]: expected={stored_answer}, got={user_answer}")
    return is_correct


async def asr_rate_limit(
        request: Request,
        token_data: Annotated[TokenData, Depends(verify_token_return_payload)]
) -> TokenData:
    """函数目的：限制用户每分钟调用 ASR 接口的次数为 20 次。
    参数信息：
        - request: Request，FastAPI 请求对象。
        - token_data: TokenData，由 verify_token_return_payload 解析得到的 JWT 载荷。
    返回值：TokenData，验证通过后原样返回供下游使用。
    """

    redis = get_redis()
    key = f"asr_limit:{token_data.id}"
    count = await redis.incr(key)

    if count == 1:
        await redis.expire(key, 60)

    if count > 20:
        logger.warning(f"ASR rate limit exceeded for user [{token_data.id}]")
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    return token_data
