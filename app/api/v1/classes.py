""" 班级相关接口 """
from typing import Annotated

from fastapi.responses import JSONResponse

from app.api.dependencies import require_teacher_or_admin
from app.common.response import response_success
from app.schema.enums import RoleType
from app.schema.user import TokenData
from app.service.organization_service import OrganizationService
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/get", description="获取自己所在组织的班级列表")
async def get_classes(
    payload: Annotated[TokenData, Depends(require_teacher_or_admin)],
    org_svc: OrganizationService = Depends(OrganizationService),
) -> JSONResponse:
    classes = []
    if payload.role == RoleType.teacher:
        org_id = await org_svc.get_teacher_org_id(payload.id)
        if org_id is not None:
            classes = await org_svc.get_classes_by_organization(org_id)
    else:
        classes = await org_svc.get_all_classes()
    return response_success({"classes": classes})
