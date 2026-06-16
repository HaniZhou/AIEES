"""全局异常拦截器（支持动态业务日志路由）"""
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from app.core.logging import get_logger


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
    def __init__(self, code: int, message: str, log_module: str = "db"):
        assert code in (400, 403, 404, 409, 429, 500, 502), \
            f"业务异常 code 必须为 HTTP 状态码，收到: {code}"
        self.code = code
        self.message = message
        self.log_module = log_module

# 预置业务日志器（统一写入 app.log，通过名称区分模块）
system_logger = get_logger("biz.system")
upstream_logger = get_logger("biz.upstream")

#  Pydantic 参数校验拦截
async def pydantic_validation_exception_handler(request: Request, exc: RequestValidationError):
    """函数目的：拦截 Pydantic 参数校验失败，统一返回 400 业务码。
    参数信息：- request: Request, - exc: RequestValidationError
    返回值：JSONResponse
    """
    errors = exc.errors()
    error_list = []
    for err in errors:
        error_list.append({
            "loc": err.get("loc", []),
            "msg": err.get("msg", "参数格式错误"),
            "type": err.get("type", "unknown"),
        })
    # 取第一个错误作为主消息
    first_msg = error_list[0]["msg"] if error_list else "参数格式错误"
    return JSONResponse(
        status_code=400,  # 改为 400（之前是 200）
        content={
            "code": 400,
            "message": first_msg,
            "data": {
                "errors": error_list,
            }
        }
    )

#  业务异常拦截（AppBusinessException）
async def app_business_exception_handler(request: Request, exc):
    """函数目的：拦截 DB/Service 层抛出的业务阻断异常，根据携带的 log_module 写入对应业务日志。
    参数信息：- request: Request, - exc: AppBusinessException 实例（需包含 code, message, log_module 属性）
    返回值：JSONResponse
    """
    code = getattr(exc, "code", 500)
    message = getattr(exc, "message", "业务处理失败")
    log_module = getattr(exc, "log_module", "system")

    # 路由到对应业务日志器（统一写入 app.log，名称格式 "biz.{模块名}"）
    target_logger = get_logger(f"biz.{log_module}")
    _log_exception(target_logger, f"Path: {request.url.path} | Biz Reject: [{code}] {message}", exc)

    # 使用真实 HTTP 状态码
    http_status = code if code in (400, 403, 404, 409, 429, 500, 502) else 400
    return JSONResponse(
        status_code=http_status,
        content={"code": code, "message": message, "data": {}}
    )

#  HTTP 异常拦截
async def http_exception_handler(request: Request, exc: HTTPException):
    """函数目的：拦截主动抛出的 HTTP 异常（如鉴权失败、上游超时）。
    参数信息：- request: Request, - exc: HTTPException
    返回值：JSONResponse
    """
    status_code = exc.status_code

    # 401/403：鉴权/越权错误，返回对应 HTTP 状态码
    if status_code in (401, 403):
        return JSONResponse(
            status_code=status_code,
            content={"code": status_code, "message": exc.detail, "data": {}}
        )

    # 500/502：系统错误，记日志，返回安全提示
    if status_code in (500, 502):
        safe_message = "上游服务暂时不可用" if status_code == 502 else "服务器内部错误"
        target = upstream_logger if status_code == 502 else system_logger
        _log_exception(target, f"Path: {request.url.path} | HTTP {status_code}: {exc.detail}", exc)
        return JSONResponse(
            status_code=status_code,
            content={"code": status_code, "message": safe_message, "data": {}}
        )

    # 其他 HTTP 错误：返回安全消息，不泄漏 exc.detail
    _log_exception(system_logger, f"Path: {request.url.path} | HTTP {status_code}: {exc.detail}", exc)
    safe_message = f"请求错误 ({status_code})"
    return JSONResponse(
        status_code=status_code,
        content={"code": status_code, "message": safe_message, "data": {}}
    )

#  4. 兜底系统异常拦截 
async def global_system_exception_handler(request: Request, exc: Exception):
    """函数目的：拦截所有未被上述处理器捕获的系统级异常，防止堆栈泄漏。
    参数信息：- request: Request, - exc: Exception
    返回值：JSONResponse
    """
    safe_message = "服务器内部错误"
    # 记录异常类型和路径，不记录 str(exc) 以防敏感信息泄漏
    _log_exception(system_logger, f"Path: {request.url.path} | Uncaught Exception", exc)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": safe_message, "data": {}}
    )
