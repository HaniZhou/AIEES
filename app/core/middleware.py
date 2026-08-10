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
        except Exception as exc:
            # 兜底日志：只记单行摘要，不附堆栈。
            # 全堆栈由 global_system_exception_handler 统一记入 biz.system，避免同一异常重复记录。
            # 不记录登录失败/验证码等敏感信息；ASR 中间态失败由 ai_client 自行记录，
            # 此处仅兜底异常处理器无法转换的异常（如 SSE 推流中途断开的异常）以及处理器自身的异常。
            logger.error(
                "✗ %s %s 未捕获异常: %s",
                request.method, request.url.path, type(exc).__name__,
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
