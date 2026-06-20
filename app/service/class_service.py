from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.exceptions import AppBusinessException
from app.model.models import StudentClass
from fastapi import Depends


class ClassService:
    """班级管理"""

    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session

    async def create(self, class_name: str, organization_id: int) -> tuple[int, int]:
        stmt = select(StudentClass).where(
            StudentClass.class_name == class_name,
            StudentClass.organization_id == organization_id,
        )
        existing = (await self.session.exec(stmt)).one_or_none()
        if existing:
            return (existing.class_id, existing.organization_id)
        cls = StudentClass(class_name=class_name, organization_id=organization_id)
        self.session.add(cls)
        await self.session.flush()
        await self.session.refresh(cls)
        return (cls.class_id, cls.organization_id)

    async def get_class_id(self, class_name: str, organization_id: int) -> int:
        stmt = select(StudentClass).where(
            StudentClass.class_name == class_name,
            StudentClass.organization_id == organization_id,
        )
        cls = (await self.session.exec(stmt)).one_or_none()
        if not cls:
            raise AppBusinessException(400, "该组织下不存在此班级，学生无法加入")
        return cls.class_id

    async def create_direct(self, class_name: str, organization_id: int) -> int:
        cls = StudentClass(class_name=class_name, organization_id=organization_id)
        self.session.add(cls)
        await self.session.flush()
        await self.session.refresh(cls)
        return cls.class_id

    async def update(self, class_id: int, update_data: dict) -> None:
        stmt = select(StudentClass).where(StudentClass.class_id == class_id)
        cls = (await self.session.exec(stmt)).one_or_none()
        if not cls:
            raise AppBusinessException(404, "班级不存在")
        for key, value in update_data.items():
            if hasattr(cls, key) and value is not None:
                setattr(cls, key, value)
        self.session.add(cls)
        await self.session.flush()

    async def delete(self, class_id: int) -> bool:
        stmt = select(StudentClass).where(StudentClass.class_id == class_id)
        cls = (await self.session.exec(stmt)).one_or_none()
        if not cls:
            raise AppBusinessException(404, "班级不存在")
        await self.session.delete(cls)
        await self.session.flush()
        return True
