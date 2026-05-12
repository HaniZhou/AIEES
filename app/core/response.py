"""
全局统一响应构造器 (Single Source of Truth)
规范要求：严禁在任何路由文件中手搓 JSONResponse 结构，必须统一使用此模块。
"""
from fastapi.responses import JSONResponse
from fastapi import status
from typing import Any


def _success(data: Any = None) -> JSONResponse:
    """规范：成功响应信封，严禁返回 null，空数据默认为 {}"""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"code": 200, "data": data if data is not None else {}}
    )


def _error(code: int, message: str, data: Any = None) -> JSONResponse:
    """
    规范：业务级错误(400/404等)必须作为 JSON Body 返回，HTTP 状态码统一 200。
    参数信息：
        - code: int，业务错误码。
        - message: str，错误提示信息。
        - data: Any | None，可选的附加数据（如 need_captcha、lock_ttl 等状态字段），
                为 None 时返回空对象 {}，严禁返回 null。
    返回值：JSONResponse。
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"code": code, "message": message, "data": data if data is not None else {}}
    )


def _created(data: Any = None) -> JSONResponse:
    """规范：资源创建成功时使用 201 状态码，但响应体仍遵循标准信封"""
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"code": 201, "data": data if data is not None else {}}
    )
