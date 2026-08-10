"""
登录限流与账号锁定模块
"""

from typing import Annotated

from app.core.config import AuthSecurityConfig
from app.core.logging import get_logger
from app.core.redis import redis_client
from app.core.security import verify_token_return_payload
from app.schema.user import TokenData
from fastapi import Depends, HTTPException, Request

logger = get_logger(__name__)


class RateLimiter:
    def __init__(self):
        self._cli = redis_client.get_client()
        self._captcha_prefix = "auth:captcha:"
        self._fail_prefix = "auth:login_fail:"
        self._lock_prefix = "auth:login_lock:"
        self._asr_prefix = "asr_limit:"

    def _captcha_key(self, captcha_key: str) -> str:
        """生成验证码 Redis Key"""
        return f"{self._captcha_prefix}{captcha_key}"

    def _fail_count_key(self, user_id: str) -> str:
        """生成失败计数 Redis Key"""
        return f"{self._fail_prefix}{user_id}"

    def _lock_key(self, user_id: str) -> str:
        """生成账号锁定 Redis Key"""
        return f"{self._lock_prefix}{user_id}"

    def _asr_limit_key(self, user_id: str) -> str:
        """生成 ASR 限流 Redis Key"""
        return f"{self._asr_prefix}{user_id}"

    async def check_login_status(self, user_id: str) -> dict:
        """检查账号当前登录状态（正常 / 需验证码 / 已锁定）"""
        lk = self._lock_key(user_id)
        ttl = await self._cli.ttl(lk)
        if ttl > 0:
            return {
                "status": "locked",
                "fail_count": AuthSecurityConfig.FAIL_THRESHOLD_LOCK,
                "lock_ttl": ttl,
            }

        fk = self._fail_count_key(user_id)
        fail_count_str = await self._cli.get(fk)
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

    async def record_login_failure(self, user_id: str) -> dict:
        """记录一次登录失败，累计失败次数达阈值时触发锁定"""
        fk = self._fail_count_key(user_id)
        fail_count = await self._cli.incr(fk)

        if fail_count == 1:
            await self._cli.expire(fk, AuthSecurityConfig.LOGIN_FAIL_COUNT_TTL)

        if fail_count >= AuthSecurityConfig.FAIL_THRESHOLD_LOCK:
            lk = self._lock_key(user_id)
            await self._cli.set(lk, "1", ex=AuthSecurityConfig.LOGIN_LOCK_TTL)
            return {"status": "locked", "fail_count": fail_count}

        return {
            "status": "need_captcha" if fail_count >= AuthSecurityConfig.FAIL_THRESHOLD_CAPTCHA else "normal",
            "fail_count": fail_count,
        }

    async def clear_login_failures(self, user_id: str) -> None:
        """登录成功后清除该用户的失败计数记录"""
        fk = self._fail_count_key(user_id)
        await self._cli.delete(fk)

    async def store_captcha(self, captcha_key: str, answer: int) -> None:
        """将验证码正确答案存入 Redis，设置过期时间"""
        key = self._captcha_key(captcha_key)
        await self._cli.set(key, str(answer), ex=AuthSecurityConfig.CAPTCHA_TTL)

    async def verify_captcha(self, captcha_key: str, user_answer: str) -> bool:
        """验证用户提交的验证码，验证后立即删除防止重放"""
        key = self._captcha_key(captcha_key)
        stored_answer = await self._cli.get(key)

        await self._cli.delete(key)

        if not stored_answer:
            return False

        is_correct = stored_answer.strip().lower() == user_answer.strip().lower()
        return is_correct

    async def asr_rate_limit(
        self, request: Request, token_data: Annotated[TokenData, Depends(verify_token_return_payload)]
    ) -> TokenData:
        """限制用户每分钟调用 ASR 接口次数（默认 20 次）"""
        key = self._asr_limit_key(token_data.id)
        count: int = await self._cli.incr(key)

        if count == 1:
            await self._cli.expire(key, 60)

        if count > 20:
            logger.warning(f"ASR rate limit exceeded for user [{token_data.id}]")
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

        return token_data

rate_limiter = RateLimiter()
