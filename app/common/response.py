"""
全局统一成功响应构造器 (Single Source of Truth)
规范要求：严禁在任何路由文件中手搓 JSONResponse 结构，必须统一使用此模块。
错误响应由 core/exceptions._build_error_response 构造，路由层 raise AppBusinessException。
"""

from typing import Any

from fastapi.responses import JSONResponse

from fastapi import status


def response_success(data: Any = None) -> JSONResponse:
    """规范：成功响应信封，严禁返回 null，空数据默认为 {}"""
    return JSONResponse(status_code=status.HTTP_200_OK, content={"code": 200, "data": data if data is not None else {}})


def response_created(data: Any = None) -> JSONResponse:
    """规范：资源创建成功时使用 201 状态码，但响应体仍遵循标准信封"""
    return JSONResponse(
        status_code=status.HTTP_201_CREATED, content={"code": 201, "data": data if data is not None else {}}
    )
