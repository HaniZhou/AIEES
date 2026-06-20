"""全局异常拦截器（支持动态业务日志路由）"""

import logging

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from fastapi import HTTPException, Request


# 统一日志记录工具
def _log_exception(logger: logging.Logger, message: str, exc: BaseException | None = None):
    """安全记录异常：只记录异常类型和消息，不记录敏感参数。"""
    if exc:
        safe_msg = f"{message} | Type: {type(exc).__name__}"
        logger.error(safe_msg, exc_info=True)
    else:
        logger.error(message)


# 纯业务异常定义
class AppBusinessException(Exception):
    """业务阻断异常。
    code 参数必须使用真实 HTTP 状态码:
        400 - 参数错误/业务冲突
        403 - 无权限
        404 - 资源不存在
        409 - 资源冲突（如已提交过答案）
        429 - 频率限制
        500 - 系统内部错误
        502 - 上游服务错误
    """

    def __init__(self, code: int, message: str, data: dict | None = None, log_module: str = "db"):
        assert code in (400, 403, 404, 409, 429, 500, 502), f"业务异常 code 必须为 HTTP 状态码，收到: {code}"
        self.code = code
        self.message = message
        self.data = data if data is not None else {}
        self.log_module = log_module


# 错误响应构造器（内部使用，路由层通过 raise AppBusinessException 走全局拦截器统一处理）
def _build_error_response(code: int, message: str, data: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=code, content={"code": code, "message": message, "data": data if data is not None else {}}
    )


# 预置业务日志器（统一写入 app.log，通过名称区分模块）
system_logger = get_logger("biz.system")
upstream_logger = get_logger("biz.upstream")


#  Pydantic 参数校验拦截
async def pydantic_validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    error_list = []
    for err in errors:
        error_list.append(
            {
                "loc": err.get("loc", []),
                "msg": err.get("msg", "参数格式错误"),
                "type": err.get("type", "unknown"),
            }
        )
    first_msg = error_list[0]["msg"] if error_list else "参数格式错误"
    return _build_error_response(400, first_msg, {"errors": error_list})


#  业务异常拦截（AppBusinessException）
async def app_business_exception_handler(request: Request, exc):
    code = getattr(exc, "code", 500)
    message = getattr(exc, "message", "业务处理失败")
    log_module = getattr(exc, "log_module", "system")

    target_logger = get_logger(f"biz.{log_module}")

    if code >= 500:
        # 5xx: 全堆栈（需要排查）
        _log_exception(target_logger, f"Path: {request.url.path} | Biz Reject: [{code}] {message}", exc)
    else:
        # 4xx: 单行警告（预期行为）
        target_logger.warning("Path: %s | Biz Reject: [%d] %s", request.url.path, code, message)

    return _build_error_response(code, message, exc.data)


#  HTTP 异常拦截
async def http_exception_handler(request: Request, exc: HTTPException):
    status_code = exc.status_code

    if status_code >= 500:
        # 5xx: 全堆栈（需要排查）
        target = upstream_logger if status_code == 502 else system_logger
        _log_exception(target, f"Path: {request.url.path} | HTTP {status_code}: {exc.detail}", exc)
    else:
        # 4xx: 单行警告（预期行为，无堆栈）
        system_logger.warning("Path: %s | HTTP %d: %s", request.url.path, status_code, exc.detail)

    safe_message = (
        "上游服务暂时不可用" if status_code == 502 else "服务器内部错误" if status_code == 500 else exc.detail
    )
    return _build_error_response(status_code, safe_message, {})


#  4. 兜底系统异常拦截
async def global_system_exception_handler(request: Request, exc: Exception):
    """函数目的：拦截所有未被上述处理器捕获的系统级异常，防止堆栈泄漏。
    参数信息：- request: Request, - exc: Exception
    返回值：JSONResponse
    """
    _log_exception(system_logger, f"Path: {request.url.path} | Uncaught Exception", exc)
    return _build_error_response(500, "服务器内部错误", {})
