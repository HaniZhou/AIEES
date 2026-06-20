from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.core.security import verify_password
from app.model.models import Admin, Organization, Student, StudentClass, Teacher
from app.schema.enums import RoleType
from app.schema.user import UserPublish
from fastapi import Depends

auth_logger = get_logger(__name__)


class AuthService:
    """登录、验证码、密码修改"""

    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session

    async def get_user_info(self, user_id: str, role: RoleType) -> dict | None:
        if role == RoleType.student:
            stmt = select(Student).where(Student.id == user_id)
            user = (await self.session.exec(stmt)).one_or_none()
        elif role == RoleType.teacher:
            stmt = select(Teacher).where(Teacher.id == user_id)
            user = (await self.session.exec(stmt)).one_or_none()
        else:
            stmt = select(Admin).where(Admin.id == user_id)
            user = (await self.session.exec(stmt)).one_or_none()

        if not user:
            return None

        from app.schema.enums import PhaseType
        base_info = {
            "id": user.id,
            "role": role,
            "username": user.username,
            "hashed_password": user.hashed_password,
            "student_class": "",
            "phase": PhaseType.senior,
        }

        if role == RoleType.student:
            base_info.update({"class_id": user.class_id, "organization_id": user.organization_id})
            stmt = select(StudentClass).where(StudentClass.class_id == user.class_id)
            class_obj = (await self.session.exec(stmt)).one_or_none()
            if class_obj:
                base_info["student_class"] = class_obj.class_name
            stmt = select(Organization).where(Organization.organization_id == user.organization_id)
            org_obj = (await self.session.exec(stmt)).one_or_none()
            if org_obj:
                base_info["phase"] = org_obj.phase
        elif role == RoleType.teacher:
            base_info.update({"organization_id": user.organization_id})
            stmt = select(Organization).where(Organization.organization_id == user.organization_id)
            org_obj = (await self.session.exec(stmt)).one_or_none()
            if org_obj:
                base_info["phase"] = org_obj.phase

        return base_info

    async def update_password(self, user_id: str, role: RoleType, new_hashed_password: str) -> bool:
        if role == RoleType.student:
            stmt = select(Student).where(Student.id == user_id)
            user = (await self.session.exec(stmt)).one_or_none()
        elif role == RoleType.teacher:
            stmt = select(Teacher).where(Teacher.id == user_id)
            user = (await self.session.exec(stmt)).one_or_none()
        else:
            stmt = select(Admin).where(Admin.id == user_id)
            user = (await self.session.exec(stmt)).one_or_none()

        if not user:
            return False

        user.hashed_password = new_hashed_password
        self.session.add(user)
        await self.session.flush()
        return True

    async def authenticate_user(self, id: str, password: str, role: RoleType) -> UserPublish | None:
        """认证用户（三表查询 + 密码校验）"""
        from app.core.security import DUMMY_HASH

        user_dict = await self.get_user_info(id, role)
        if not user_dict:
            verify_password(password, DUMMY_HASH)
            auth_logger.warning(f"Login failed: user [{id}] (role={role.value}) not found in DB")
            return None
        if not verify_password(password, user_dict.get("hashed_password")):
            auth_logger.warning(f"Login failed: user [{id}] (role={role.value}) wrong password")
            return None
        user_dict.pop("hashed_password", None)
        user_dict.pop("class_id", None)
        user_dict.pop("organization_id", None)
        return UserPublish(**user_dict)
