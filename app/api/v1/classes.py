""" 班级相关接口 """
from app.crud.db import db_get_all_classes, db_get_teacher_org_id, db_get_classes_by_organization
from app.core.security import require_teacher_or_admin
from app.model.schema.schema import TokenData, RoleType
from fastapi.responses import JSONResponse
from fastapi import Depends, status, APIRouter
from typing import Annotated

router = APIRouter()

#  统一响应构造器 

def _success(data=None) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_200_OK, content={"code": 200, "data": data if data is not None else {}})

#  接口实现 

@router.get("/get", description="获取自己所在组织的班级列表")
async def get_classes(payload: Annotated[TokenData, Depends(require_teacher_or_admin)]) -> JSONResponse:
    classes = []
    if payload.role == RoleType.teacher:
        org_id = await db_get_teacher_org_id(payload.id)
        if org_id is not None:
            classes = await db_get_classes_by_organization(org_id)
    else:
        # 管理员获取所有班级
        classes = await db_get_all_classes()

    # 无论是否为空列表，必须严格走 _success 信封，严禁裸返回 {"classes": []}
    return _success({"classes": classes})
