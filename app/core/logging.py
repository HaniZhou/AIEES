"""
日志系统统一配置。
所有模块通过 import 此模块的 logger 或使用 get_logger() 获取 Logger。
"""

import logging
import os
import sys
from contextvars import ContextVar

# 日志级别（通过环境变量配置，默认 INFO）
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
SLOW_QUERY_MS = int(os.getenv("SLOW_QUERY_MS", "500"))
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_LOG_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s] [rid=%(request_id)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class RequestIDFilter(logging.Filter):
    """
    日志 Filter：向 LogRecord 注入 request_id。
    从 contextvars 中读取当前请求的关联 ID，若不存在则为 "-"。
    """
    def filter(self, record):
        try:
            record.request_id = request_id_var.get()
        except LookupError:
            record.request_id = "-"
        return True


def configure_logging():
    """配置根 Logger（应用启动时调用一次）。"""
    # 根 Logger 配置
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # 清除已有 handlers（防止重复配置）
    root_logger.handlers.clear()

    # 控制台 Handler（Docker 日志）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL)
    console_handler.setFormatter(logging.Formatter(
        _LOG_FORMAT, datefmt=_DATE_FORMAT
    ))
    console_handler.addFilter(RequestIDFilter())
    root_logger.addHandler(console_handler)

    # 第三方库日志降级（避免 uvicorn/sqlalchemy 刷屏）
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取 Logger 实例（模块使用 __name__ 传入）。"""
    return logging.getLogger(name)
