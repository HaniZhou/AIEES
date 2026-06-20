from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应模型"""
    code: int = 200
    message: str = ""
    data: T = None


class PageParams(BaseModel):
    """分页请求参数"""
    page: int = 1
    size: int = 30


class PageResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: list[T]
    total: int
    page: int
    size: int
    total_pages: int
