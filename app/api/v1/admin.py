from typing import Annotated

from app.api.dependencies import require_admin
from app.core.exceptions import AppBusinessException
from app.common.response import response_created, response_success
from app.core.logging import get_logger
from app.core.security import get_password_hash
from app.schema.admin import StudentUpdate, TeacherUpdate
from app.schema.class_ import ClassCreate, ClassUpdate, DeleteClassRequest
from app.schema.organization import DeleteOrgRequest, OrganizationCreate, OrganizationUpdate
from app.schema.user import DeleteUserRequest, RoleType, StudentRegister, TeacherRegister, TokenData, UserInDB
from app.service.class_service import ClassService
from app.service.organization_service import OrganizationService
from app.service.user_service import UserService
from fastapi import APIRouter, Depends, Response

router = APIRouter()
admin_route_logger = get_logger(__name__)


#  管理员：用户与组织管理


@router.post("/organization/new")
async def create_new_organization(
    org_info: OrganizationCreate,
    payload: Annotated[TokenData, Depends(require_admin)],
    org_svc: OrganizationService = Depends(OrganizationService),
):
    org_id = await org_svc.create(org_info.organization_name, phase=org_info.phase, prefix=org_info.prefix)
    return response_success({"organization_id": org_id})


@router.delete("/organization/delete")
async def delete_organization(
    req: DeleteOrgRequest,
    payload: Annotated[TokenData, Depends(require_admin)],
    org_svc: OrganizationService = Depends(OrganizationService),
):
    await org_svc.delete(req.organization_id)
    return response_success({})


@router.post("/user/new/student")
async def create_new_student(
    register_info: StudentRegister,
    payload: Annotated[TokenData, Depends(require_admin)],
    user_svc: UserService = Depends(UserService),
    org_svc: OrganizationService = Depends(OrganizationService),
    class_svc: ClassService = Depends(ClassService),
) -> Response:
    hashed_password = get_password_hash(register_info.password)
    org_id = await org_svc.get_id_by_name(register_info.organization_name)
    class_id = await class_svc.get_class_id(register_info.student_class, org_id)

    is_success = await user_svc.create_student(
        UserInDB(
            id=register_info.id,
            role=RoleType.student,
            username=register_info.username,
            hashed_password=hashed_password,
            class_id=class_id,
            organization_id=org_id,
        )
    )
    if not is_success:
        raise AppBusinessException(409, "用户已存在")
    return response_created({})


@router.delete("/user/delete/student")
async def delete_student(
    req: DeleteUserRequest,
    payload: Annotated[TokenData, Depends(require_admin)],
    user_svc: UserService = Depends(UserService),
):
    await user_svc.delete_student(req.id)
    return response_success({})


@router.post("/user/new/teacher")
async def create_new_teacher(
    register_info: TeacherRegister,
    payload: Annotated[TokenData, Depends(require_admin)],
    user_svc: UserService = Depends(UserService),
    org_svc: OrganizationService = Depends(OrganizationService),
) -> Response:
    hashed_password = get_password_hash(register_info.password)
    org_id = await org_svc.get_id_by_name(register_info.organization_name)

    is_success = await user_svc.create_teacher(
        UserInDB(
            id=register_info.id,
            role=RoleType.teacher,
            hashed_password=hashed_password,
            username=register_info.username,
            organization_id=org_id,
        )
    )
    if not is_success:
        raise AppBusinessException(409, "用户已存在")
    return response_created({})


@router.delete("/user/delete/teacher")
async def delete_teacher(
    req: DeleteUserRequest,
    payload: Annotated[TokenData, Depends(require_admin)],
    user_svc: UserService = Depends(UserService),
):
    await user_svc.delete_teacher(req.id)
    return response_success({})


#  管理员：班级增删改查


@router.post("/class/new")
async def create_new_class(
    req: ClassCreate,
    payload: Annotated[TokenData, Depends(require_admin)],
    org_svc: OrganizationService = Depends(OrganizationService),
    class_svc: ClassService = Depends(ClassService),
) -> Response:
    await org_svc.get_by_id(req.organization_id)
    class_id = await class_svc.create_direct(class_name=req.class_name, organization_id=req.organization_id)
    return response_created({"class_id": class_id})


@router.delete("/class/delete")
async def delete_class(
    req: DeleteClassRequest,
    payload: Annotated[TokenData, Depends(require_admin)],
    class_svc: ClassService = Depends(ClassService),
):
    await class_svc.delete(req.class_id)
    return response_success({})


@router.get("/class/page")
async def get_classes_page(
    payload: Annotated[TokenData, Depends(require_admin)],
    organization_id: int,
    page: int = 1,
    size: int = 30,
    keyword: str | None = None,
    org_svc: OrganizationService = Depends(OrganizationService),
):
    result = await org_svc.get_classes_page(organization_id=organization_id, page=page, size=size, keyword=keyword)
    return response_success(result)


@router.patch("/class/update")
async def update_class(
    req: ClassUpdate,
    payload: Annotated[TokenData, Depends(require_admin)],
    class_svc: ClassService = Depends(ClassService),
):
    update_data = req.model_dump(exclude={"class_id"}, exclude_unset=True)
    await class_svc.update(class_id=req.class_id, update_data=update_data)
    return response_success({})


#  管理员：组织分页与修改


@router.get("/organization/page")
async def get_organizations_page(
    payload: Annotated[TokenData, Depends(require_admin)],
    page: int = 1,
    size: int = 30,
    keyword: str | None = None,
    org_svc: OrganizationService = Depends(OrganizationService),
):
    result = await org_svc.paginate_organizations(page=page, size=size, keyword=keyword)
    return response_success(result)


@router.patch("/organization/update")
async def update_organization(
    req: OrganizationUpdate,
    payload: Annotated[TokenData, Depends(require_admin)],
    org_svc: OrganizationService = Depends(OrganizationService),
):
    update_data = req.model_dump(exclude={"organization_id"}, exclude_unset=True)
    await org_svc.update(org_id=req.organization_id, update_data=update_data)
    return response_success({})


#  管理员：教师分页与修改


@router.get("/user/page/teacher")
async def get_teachers_page(
    payload: Annotated[TokenData, Depends(require_admin)],
    organization_id: int,
    page: int = 1,
    size: int = 30,
    keyword: str | None = None,
    org_svc: OrganizationService = Depends(OrganizationService),
):
    result = await org_svc.get_teachers_page(organization_id=organization_id, page=page, size=size, keyword=keyword)
    return response_success(result)


@router.patch("/user/update/teacher")
async def update_teacher_info(
    req: TeacherUpdate,
    payload: Annotated[TokenData, Depends(require_admin)],
    user_svc: UserService = Depends(UserService),
):
    update_data = req.model_dump(exclude={"id"}, exclude_unset=True)
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    else:
        update_data.pop("password", None)

    await user_svc.update_teacher(teacher_id=req.id, update_data=update_data)
    return response_success({})


#  管理员：学生分页与修改


@router.get("/user/page/student")
async def get_students_page(
    payload: Annotated[TokenData, Depends(require_admin)],
    class_id: int,
    page: int = 1,
    size: int = 30,
    keyword: str | None = None,
    org_svc: OrganizationService = Depends(OrganizationService),
):
    result = await org_svc.get_students_page(class_id=class_id, page=page, size=size, keyword=keyword)
    return response_success(result)


@router.patch("/user/update/student")
async def update_student_info(
    req: StudentUpdate,
    payload: Annotated[TokenData, Depends(require_admin)],
    user_svc: UserService = Depends(UserService),
):
    update_data = req.model_dump(exclude={"id", "class_id"}, exclude_unset=True)

    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    else:
        update_data.pop("password", None)

    target_class = req.class_id if "class_id" in req.model_fields_set else None

    await user_svc.update_student(student_id=req.id, update_data=update_data, target_class_id=target_class)
    return response_success({})
