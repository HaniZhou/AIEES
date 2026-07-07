"""
请求关联 ID Middleware：
1. 每个请求生成或透传 request_id
2. 注入 contextvars 供 Logger 使用
3. 记录异常和慢请求日志
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger, request_id_var
from fastapi import Request

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. 生成或透传 request_id
        request_id = request.headers.get(
            "X-Request-Id",
            str(uuid.uuid4())
        )
        request_id_var.set(request_id)

        # 2. 执行请求并计时
        start_time = time.time()
        try:
            response = await call_next(request)
        except Exception: # TODO：错误日志未来在这里统一处理，避免重复记录；或者做拓展；考虑登陆信息需要记录吗？（我认为不用）；asr请求失败只需要记录完全失败
            logger.error(
                "✗ %s %s (unhandled exception during request)",
                request.method, request.url.path,
                exc_info=True,
            )
            raise

        duration_ms = int((time.time() - start_time) * 1000)

        # 3. 响应头带回 request_id
        response.headers["X-Request-Id"] = request_id

        # 4. 慢请求警告（超过 2 秒）
        if duration_ms > 2000:
            logger.warning(
                "%s %s %d %dms",
                request.method, request.url.path,
                response.status_code, duration_ms,
                extra={"request_id": request_id, "slow": True}
            )

        return response
