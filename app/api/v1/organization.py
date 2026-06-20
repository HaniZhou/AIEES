from app.common.response import response_success
from app.service.organization_service import OrganizationService
from fastapi import APIRouter, Depends, Query

router = APIRouter()

@router.get("/get", description="获取机构列表（登录页下拉选择用）")
async def get_organizations(
    page: int = Query(..., ge=1, description="当前页码，从 1 开始"),
    keyword: str | None = Query(default=None, description="搜索关键词（按机构名称模糊匹配）"),
    org_svc: OrganizationService = Depends(OrganizationService),
):
    data = await org_svc.paginate_organizations(page, 30, keyword)
    return response_success(data)
