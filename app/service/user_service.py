from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.common.tools import is_deletable_resource_path, remove_file, to_upload_relative_path
from app.core.database import db
from app.core.exceptions import AppBusinessException
from app.model.models import Admin, Chapter, Course, Section, Student, StudentClass, Teacher
from app.schema.user import UserInDB
from fastapi import Depends


class UserService:
    """用户创建/更新（含角色分发）"""

    def __init__(self, session: AsyncSession = Depends(db.get_session)):
        self.session = session

    async def create_student(self, user: UserInDB) -> bool:
        stmt = select(Student).where(Student.id == user.id)
        if (await self.session.exec(stmt)).one_or_none():
            return False
        student = Student(
            id=user.id, username=user.username,
            class_id=user.class_id, organization_id=user.organization_id,
            hashed_password=user.hashed_password,
        )
        self.session.add(student)
        await self.session.flush()
        return True

    async def create_teacher(self, user: UserInDB) -> bool:
        stmt = select(Teacher).where(Teacher.id == user.id)
        if (await self.session.exec(stmt)).one_or_none():
            return False
        teacher = Teacher(
            id=user.id, username=user.username,
            hashed_password=user.hashed_password,
            organization_id=user.organization_id,
        )
        self.session.add(teacher)
        await self.session.flush()
        return True

    async def create_admin(self, user: UserInDB) -> bool:
        stmt = select(Admin).where(Admin.id == user.id)
        if (await self.session.exec(stmt)).one_or_none():
            return False
        admin = Admin(id=user.id, username=user.username, hashed_password=user.hashed_password)
        self.session.add(admin)
        await self.session.flush()
        return True

    async def delete_student(self, student_id: str) -> bool:
        stmt = select(Student).where(Student.id == student_id)
        student = (await self.session.exec(stmt)).one_or_none()
        if not student:
            raise AppBusinessException(404, "学生不存在")
        await self.session.delete(student)
        await self.session.flush()
        return True

    async def delete_teacher(self, teacher_id: str) -> bool:
        stmt = select(Teacher).where(Teacher.id == teacher_id)
        teacher = (await self.session.exec(stmt)).one_or_none()
        if not teacher:
            raise AppBusinessException(404, "教师不存在")

        stmt = select(Course.course_id).where(Course.teacher_id == teacher_id)
        course_ids = list((await self.session.exec(stmt)).all())

        cover_paths = set()
        section_paths = set()
        if course_ids:
            stmt = select(Course.course_cover).where(Course.course_id.in_(course_ids))
            cover_paths = set((await self.session.exec(stmt)).all())
            stmt = select(Chapter).where(Chapter.course_id.in_(course_ids))
            chapters = (await self.session.exec(stmt)).all()
            if chapters:
                chapter_ids = [ch.chapter_id for ch in chapters]
                stmt = select(Section).where(Section.chapter_id.in_(chapter_ids))
                sections = (await self.session.exec(stmt)).all()
                section_paths = {s.resource_path for s in sections if s.resource_path}

        await self.session.delete(teacher)
        await self.session.flush()

        cover_paths = {p for p in cover_paths if p and p != "covers/default.png"}
        for path in cover_paths:
            await remove_file(path)

        if section_paths:
            safe_paths = {p for p in section_paths if p and is_deletable_resource_path(p)}
            if safe_paths:
                stmt = select(Section.resource_path).where(Section.resource_path.in_(safe_paths))
                referenced = set((await self.session.exec(stmt)).all())
                orphaned = safe_paths - referenced
                for path in orphaned:
                    await remove_file(to_upload_relative_path(path))

        return True

    async def update_teacher(self, teacher_id: str, update_data: dict) -> None:
        stmt = select(Teacher).where(Teacher.id == teacher_id)
        teacher = (await self.session.exec(stmt)).one_or_none()
        if not teacher:
            raise AppBusinessException(404, "教师不存在")
        for key, value in update_data.items():
            if hasattr(teacher, key) and value is not None:
                setattr(teacher, key, value)
        self.session.add(teacher)
        await self.session.flush()

    async def update_student(self, student_id: str, update_data: dict, target_class_id: int | None = None) -> None:
        stmt = select(Student).where(Student.id == student_id)
        student = (await self.session.exec(stmt)).one_or_none()
        if not student:
            raise AppBusinessException(404, "学生不存在")

        if target_class_id is not None:
            stmt = select(StudentClass).where(StudentClass.class_id == target_class_id)
            target_class = (await self.session.exec(stmt)).one_or_none()
            if not target_class:
                raise AppBusinessException(404, "目标班级不存在")
            if target_class.organization_id != student.organization_id:
                raise AppBusinessException(400, "禁止跨组织转班")
            student.class_id = target_class_id

        for key, value in update_data.items():
            if hasattr(student, key) and value is not None:
                setattr(student, key, value)
        self.session.add(student)
        await self.session.flush()
