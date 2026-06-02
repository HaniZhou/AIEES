"""全局异常拦截器（支持动态业务日志路由）"""
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from app import Config
from datetime import datetime

#  日志格式化工具 
class StrictFormatter(logging.Formatter):
    def format(self, record):
        record.asctime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"[{record.asctime}] [{record.levelname}] [{record.module}] {record.getMessage()}"

# 使用缓存防止重复创建 Handler
_logger_cache: dict[str, logging.Logger] = {}


# 纯业务异常定义
class AppBusinessException(Exception):
    """业务阻断异常：仅用于表达业务规则拒绝(404/403/400)。严禁用于表达系统故障。"""
    def __init__(self, code: int, message: str, log_module: str = "db"):
        self.code = code
        self.message = message
        self.log_module = log_module

def _setup_logger(module_name: str) -> logging.Logger:
    """函数目的：根据模块名获取或创建对应的文件 Logger，确保日志物理隔离。
    参数信息：- module_name: str，日志模块名（如 'db', 'ai'），对应文件为 {module_name}.log。
    返回值：logging.Logger 实例。
    """
    if module_name in _logger_cache:
        return _logger_cache[module_name]

    logger = logging.getLogger(module_name)
    logger.setLevel(logging.ERROR)
    if not logger.handlers:
        log_file = Config.UrlConfig.LOGS_DIR / f"{module_name}.log"
        if not log_file.parent.exists():
            log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(StrictFormatter())
        logger.addHandler(handler)

    _logger_cache[module_name] = logger
    return logger

# 预置系统与上游日志器
system_logger = _setup_logger("system")
upstream_logger = _setup_logger("upstream")

#  Pydantic 参数校验拦截
async def pydantic_validation_exception_handler(request: Request, exc: RequestValidationError):
    """函数目的：拦截 Pydantic 参数校验失败，统一返回 400 业务码。
    参数信息：- request: Request, - exc: RequestValidationError
    返回值：JSONResponse
    """
    first_error = exc.errors()[0] if exc.errors() else {}
    msg = first_error.get("msg", "参数格式错误")
    return JSONResponse(
        status_code=200,
        content={"code": 400, "message": msg, "data": {}}
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

    # 动态路由到具体的业务日志文件
    target_logger = _setup_logger(log_module)
    target_logger.error(f"Path: {request.url.path} | Biz Reject: [{code}] {message}")

    return JSONResponse(
        status_code=200,  # 规范：业务错误统一 HTTP 200，错误码放在 JSON body
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
        log_msg = f"Path: {request.url.path} | Error: {exc.detail}"
        if status_code == 502:
            upstream_logger.error(log_msg)
        else:
            system_logger.error(log_msg)
        safe_message = "上游服务暂时不可用" if status_code == 502 else "服务器内部错误"
        return JSONResponse(
            status_code=status_code,
            content={"code": status_code, "message": safe_message, "data": {}}
        )

    # 其他 HTTP 错误
    return JSONResponse(
        status_code=status_code,
        content={"code": status_code, "message": exc.detail, "data": {}}
    )

#  4. 兜底系统异常拦截 
async def global_system_exception_handler(request: Request, exc: Exception):
    """函数目的：拦截所有未被上述处理器捕获的系统级异常，防止堆栈泄漏。
    参数信息：- request: Request, - exc: Exception
    返回值：JSONResponse
    """
    log_msg = f"Path: {request.url.path} | Uncaught Exception: {str(exc)}"
    system_logger.error(log_msg)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误", "data": {}}
    )
