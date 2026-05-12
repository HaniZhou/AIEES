"""认证相关接口"""
import logging

from fastapi import APIRouter, Response, Depends
from typing import Annotated

from app.crud.db import (
    db_insert_new_student,
    db_insert_new_teacher,
    db_get_class_id_in_organization,
    db_get_organization_id_by_name,
    db_delete_teacher,
    db_delete_student,
    db_delete_organization,
    db_delete_class,
    db_create_new_organization,
    db_get_organizations_page, db_update_organization,
    db_get_classes_page, db_create_class_direct, db_update_class,
    db_get_teachers_page, db_update_teacher,
    db_get_students_page, db_update_student
)
from app.core.security import (
    get_password_hash,
    require_admin,
)
from app.model.schema.schema import (
    TokenData,
    OrganizationUpdate, ClassCreate, ClassUpdate, TeacherUpdate, StudentUpdate,
    DeleteOrgRequest, DeleteClassRequest,
    OrganizationCreate, UserInDB, RoleType, StudentRegister, TeacherRegister, DeleteUserRequest
)

from app.core.response import _success, _error, _created

router = APIRouter()
admin_route_logger = logging.getLogger("admin.route")


#  管理员：用户与组织管理

@router.post("/organization/new")
async def create_new_organization(
        org_info: OrganizationCreate,
        payload: Annotated[TokenData, Depends(require_admin)],
):
    """
    函数目的：管理员创建新机构（学段为必填项）。
    参数信息：
        - org_info: OrganizationCreate, 机构信息（含学段和前缀）。
        - payload: TokenData, 由 require_admin 依赖注入（确保管理员权限）。
    返回值：统一响应。
    """
    org_id = await db_create_new_organization(
        org_info.organization_name, phase=org_info.phase, prefix=org_info.prefix
    )
    return _success({"organization_id": org_id})


@router.delete("/organization/delete")
async def delete_organization(
        req: DeleteOrgRequest,
        payload: Annotated[TokenData, Depends(require_admin)],
):
    """
    函数目的：管理员删除组织及其所有关联数据。
    参数信息：
        - req: DeleteOrgRequest, 包含要删除的组织 ID。
        - payload: TokenData, 管理员身份凭证。
    返回值：统一响应。
    """
    await db_delete_organization(req.organization_id)
    return _success({})


@router.post("/user/new/student")
async def create_new_student(
        register_info: StudentRegister,
        payload: Annotated[TokenData, Depends(require_admin)],
) -> Response:
    """
    函数目的：管理员创建新学生账号。
    参数信息：
        - register_info: StudentRegister, 学生注册信息。
        - payload: TokenData, 管理员身份凭证。
    返回值：创建成功返回 201，否则返回业务错误。
    """
    hashed_password = get_password_hash(register_info.password)
    # 底层 db 函数查不到会直接抛 400 异常，此处无需判空
    org_id = await db_get_organization_id_by_name(register_info.organization_name)
    class_id = await db_get_class_id_in_organization(register_info.student_class, org_id)

    is_success = await db_insert_new_student(
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
        return _error(409, "用户已存在")
    return _created({})


@router.delete("/user/delete/student")
async def delete_student(
        req: DeleteUserRequest,
        payload: Annotated[TokenData, Depends(require_admin)],
):
    """
    函数目的：管理员删除学生账号。
    参数信息：
        - req: DeleteUserRequest, 包含要删除的学生 ID。
        - payload: TokenData, 管理员身份凭证。
    返回值：统一响应。
    """
    await db_delete_student(req.id)
    return _success({})


@router.post("/user/new/teacher")
async def create_new_teacher(
        register_info: TeacherRegister,
        payload: Annotated[TokenData, Depends(require_admin)],
) -> Response:
    """
    函数目的：管理员创建新教师账号。
    参数信息：
        - register_info: TeacherRegister, 教师注册信息。
        - payload: TokenData, 管理员身份凭证。
    返回值：创建成功返回 201，否则返回业务错误。
    """
    hashed_password = get_password_hash(register_info.password)
    # 底层 db 函数查不到会直接抛 400 异常，此处无需判空
    org_id = await db_get_organization_id_by_name(register_info.organization_name)

    is_success = await db_insert_new_teacher(
        UserInDB(
            id=register_info.id,
            role=RoleType.teacher,
            hashed_password=hashed_password,
            username=register_info.username,
            organization_id=org_id,
        )
    )
    if not is_success:
        return _error(409, "用户已存在")
    return _created({})


@router.delete("/user/delete/teacher")
async def delete_teacher(
        req: DeleteUserRequest,
        payload: Annotated[TokenData, Depends(require_admin)],
):
    """
    函数目的：管理员删除教师账号及其关联课程资源。
    参数信息：
        - req: DeleteUserRequest, 包含要删除的教师 ID。
        - payload: TokenData, 管理员身份凭证。
    返回值：统一响应。
    """
    await db_delete_teacher(req.id)
    return _success({})


#  管理员：班级增删改查 

@router.post("/class/new")
async def create_new_class(
        req: ClassCreate,
        payload: Annotated[TokenData, Depends(require_admin)]
) -> Response:
    """函数目的：在指定组织下创建新班级。
    参数信息：
        - req: ClassCreate, 包含班级名称和组织ID。
        - payload: TokenData, 管理员身份凭证。
    返回值：创建成功返回 201。
    """
    await db_create_class_direct(class_name=req.class_name, organization_id=req.organization_id)
    return _created({})


@router.delete("/class/delete")
async def delete_class(
        req: DeleteClassRequest,
        payload: Annotated[TokenData, Depends(require_admin)],
):
    """
    函数目的：管理员删除班级。
    参数信息：
        - req: DeleteClassRequest, 包含要删除的班级 ID。
        - payload: TokenData, 管理员身份凭证。
    返回值：统一响应。
    """
    await db_delete_class(req.class_id)
    return _success({})


@router.get("/class/page")
async def get_classes_page(
        payload: Annotated[TokenData, Depends(require_admin)],
        organization_id: int,
        page: int = 1,
        size: int = 30,
        keyword: str | None = None,
):
    """函数目的：分页获取指定组织下的班级列表。
    参数信息：
        - organization_id: int, 必传的组织ID筛选条件。
        - page: int, 页码。
        - size: int, 每页数量。
        - keyword: str | None, 班级名搜索词。
        - payload: TokenData, 管理员身份凭证。
    返回值：包含 list 和 total 的分页统一响应。
    """
    result = await db_get_classes_page(organization_id=organization_id, page=page, size=size, keyword=keyword)
    return _success(result)


@router.patch("/class/update")
async def update_class(
        req: ClassUpdate,
        payload: Annotated[TokenData, Depends(require_admin)]
):
    """函数目的：修改班级名称。
    参数信息：
        - req: ClassUpdate, 包含班级ID和新名称。
        - payload: TokenData, 管理员身份凭证。
    返回值：统一响应。
    """
    update_data = req.model_dump(exclude={"class_id"}, exclude_unset=True)
    await db_update_class(class_id=req.class_id, update_data=update_data)
    return _success({})


#  管理员：组织分页与修改 

@router.get("/organization/page")
async def get_organizations_page(
        payload: Annotated[TokenData, Depends(require_admin)],
        page: int = 1,
        size: int = 30,
        keyword: str | None = None,
):
    """函数目的：分页获取组织列表，支持名称模糊搜索。
    参数信息：
        - page: int, 页码。
        - size: int, 每页数量。
        - keyword: str | None, 搜索词。
        - payload: TokenData, 管理员身份凭证。
    返回值：包含 list 和 total 的分页统一响应。
    """
    result = await db_get_organizations_page(page=page, size=size, keyword=keyword)
    return _success(result)


@router.patch("/organization/update")
async def update_organization(
        req: OrganizationUpdate,
        payload: Annotated[TokenData, Depends(require_admin)]
):
    """函数目的：修改组织的基础信息（含学段）。
    参数信息：
        - req: OrganizationUpdate, 更新载荷。
        - payload: TokenData, 管理员身份凭证。
    返回值：统一响应。
    """
    update_data = req.model_dump(exclude={"organization_id"}, exclude_unset=True)
    await db_update_organization(org_id=req.organization_id, update_data=update_data)
    return _success({})


#  管理员：教师分页与修改 

@router.get("/user/page/teacher")
async def get_teachers_page(
        payload: Annotated[TokenData, Depends(require_admin)],
        organization_id: int,
        page: int = 1,
        size: int = 30,
        keyword: str | None = None,
):
    """函数目的：分页获取指定组织下的教师列表。
    参数信息：
        - organization_id: int, 必传的组织ID筛选条件。
        - page: int, 页码。
        - size: int, 每页数量。
        - keyword: str | None, 教师ID或姓名搜索词。
        - payload: TokenData, 管理员身份凭证。
    返回值：包含 list 和 total 的分页统一响应。
    """
    result = await db_get_teachers_page(organization_id=organization_id, page=page, size=size, keyword=keyword)
    return _success(result)


@router.patch("/user/update/teacher")
async def update_teacher_info(
        req: TeacherUpdate,
        payload: Annotated[TokenData, Depends(require_admin)]
):
    """函数目的：修改教师用户名或重置密码。
    参数信息：
        - req: TeacherUpdate, 包含教师ID及要修改的字段。
        - payload: TokenData, 管理员身份凭证。
    返回值：统一响应。
    """
    update_data = req.model_dump(exclude={"id"}, exclude_unset=True)
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    else:
        update_data.pop("password", None)

    await db_update_teacher(teacher_id=req.id, update_data=update_data)
    return _success({})


#  管理员：学生分页与修改 

@router.get("/user/page/student")
async def get_students_page(
        payload: Annotated[TokenData, Depends(require_admin)],
        class_id: int,
        page: int = 1,
        size: int = 30,
        keyword: str | None = None,
):
    """函数目的：分页获取指定班级下的学生列表。
    参数信息：
        - class_id: int, 必传的班级ID筛选条件。
        - page: int, 页码。
        - size: int, 每页数量。
        - keyword: str | None, 学生ID或姓名搜索词。
        - payload: TokenData, 管理员身份凭证。
    返回值：包含 list 和 total 的分页统一响应。
    """
    result = await db_get_students_page(class_id=class_id, page=page, size=size, keyword=keyword)
    return _success(result)


@router.patch("/user/update/student")
async def update_student_info(
        req: StudentUpdate,
        payload: Annotated[TokenData, Depends(require_admin)]
):
    """函数目的：修改学生信息（用户名、密码、班级），转班受严格跨组织校验限制。
    参数信息：
        - req: StudentUpdate, 包含学生ID及要修改的字段。
        - payload: TokenData, 管理员身份凭证。
    返回值：统一响应。
    """
    update_data = req.model_dump(exclude={"id", "class_id"}, exclude_unset=True)

    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    else:
        update_data.pop("password", None)

    target_class = req.class_id if "class_id" in req.model_fields_set else None

    await db_update_student(
        student_id=req.id,
        update_data=update_data,
        target_class_id=target_class
    )
    return _success({})
