from app.crud.db import db_get_organizations_page
from fastapi import APIRouter,Query
from app.core.response import _success

router = APIRouter()


@router.get("/get", description="获取机构列表（登录页下拉选择用）")
async def get_organizations(
    page: int = Query(..., ge=1, description="当前页码，从 1 开始"),
    keyword: str | None = Query(default=None, description="搜索关键词（按机构名称模糊匹配）")
):
    """函数目的：处理前端获取机构分页列表的请求，无需登录鉴权。
    参数信息：
        - page: int, 页码校验由 Query(ge=1) 自动拦截。
        - keyword: str | None, 可选的搜索词。
    返回值：JSONResponse，标准信封格式包裹的机构列表。
    """
    data = await db_get_organizations_page(page,30, keyword)
    return _success(data)