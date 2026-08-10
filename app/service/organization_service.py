from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.common.pagination import paginate
from app.common.tools import is_deletable_resource_path, remove_file, to_upload_relative_path
from app.core.database import db
from app.core.exceptions import AppBusinessException
from app.model.models import (
    AnalysisTask,
    AnalysisTaskCompletion,
    Chapter,
    Course,
    CourseRegistrationRecord,
    Organization,
    Section,
    Student,
    StudentClass,
    Teacher,
)
from app.schema.class_ import ClassRead
from fastapi import Depends


class OrganizationService:
    """机构管理"""

    def __init__(self, session: AsyncSession = Depends(db.get_session)):
        self.session = session

    async def create(self, org_name: str, phase, prefix: str = "") -> int:
        stmt = select(Organization).where(Organization.organization_name == org_name)
        existing = (await self.session.exec(stmt)).one_or_none()
        if existing:
            return existing.organization_id
        org = Organization(organization_name=org_name, phase=phase, prefix=prefix.rstrip("_"))
        self.session.add(org)
        await self.session.flush()
        await self.session.refresh(org)
        return org.organization_id

    async def get_by_id(self, org_id: int):
        stmt = select(Organization).where(Organization.organization_id == org_id)
        org = (await self.session.exec(stmt)).one_or_none()
        if not org:
            raise AppBusinessException(404, "组织不存在")
        return org

    async def get_id_by_name(self, name: str) -> int:
        stmt = select(Organization).where(Organization.organization_name == name)
        org = (await self.session.exec(stmt)).one_or_none()
        if not org:
            raise AppBusinessException(400, "该组织不存在，学生无法加入")
        return org.organization_id

    async def update(self, org_id: int, update_data: dict) -> None:
        stmt = select(Organization).where(Organization.organization_id == org_id)
        org = (await self.session.exec(stmt)).one_or_none()
        if not org:
            raise AppBusinessException(404, "组织不存在")
        for key, value in update_data.items():
            if hasattr(org, key) and value is not None:
                if key == "prefix":
                    value = value.rstrip("_")
                setattr(org, key, value)
        self.session.add(org)
        await self.session.flush()

    async def delete(self, organization_id: int) -> bool:
        stmt = select(Organization).where(Organization.organization_id == organization_id)
        org = (await self.session.exec(stmt)).one_or_none()
        if not org:
            raise AppBusinessException(404, "组织不存在")

        stmt = select(Teacher.id).where(Teacher.organization_id == organization_id)
        teacher_ids = list((await self.session.exec(stmt)).all())

        cover_paths = set()
        section_paths = set()
        if teacher_ids:
            stmt = select(Course.course_id).where(Course.teacher_id.in_(teacher_ids))
            course_ids = list((await self.session.exec(stmt)).all())
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

        await self.session.delete(org)
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

    # ---- 分页查询方法（从OrganizationRepository迁移） ----

    async def paginate_organizations(self, page: int, size: int = 30, keyword: str | None = None) -> dict:
        filters = []
        if keyword:
            filters.append(Organization.organization_name.like(f"%{keyword}%"))
        rows, total = await paginate(
            self.session, Organization, page, size, filters=filters or None, order_col=Organization.organization_id
        )
        result_list = [
            {
                "organization_id": org.organization_id,
                "organization_name": org.organization_name,
                "prefix": org.prefix,
                "phase": org.phase.value,
            }
            for org in rows
        ]
        return {"list": result_list, "total": total}

    async def get_classes_page(self, organization_id: int, page: int, size: int = 30, keyword: str | None = None) -> dict:
        filters = [StudentClass.organization_id == organization_id]
        if keyword:
            filters.append(StudentClass.class_name.like(f"%{keyword}%"))
        rows, total = await paginate(
            self.session, StudentClass, page, size, filters=filters, order_col=StudentClass.class_id
        )
        result_list = [ClassRead.model_validate(c).model_dump(mode='json') for c in rows]
        return {"list": result_list, "total": total}

    async def get_teachers_page(self, organization_id: int, page: int, size: int = 30, keyword: str | None = None) -> dict:
        from sqlmodel import or_
        filters = [Teacher.organization_id == organization_id]
        if keyword:
            like_pattern = f"%{keyword}%"
            filters.append(or_(Teacher.id.like(like_pattern), Teacher.username.like(like_pattern)))
        rows, total = await paginate(self.session, Teacher, page, size, filters=filters, order_col=Teacher.id)
        result_list = [
            {"id": t.id, "username": t.username, "organization_id": t.organization_id}
            for t in rows
        ]
        return {"list": result_list, "total": total}

    async def get_students_page(self, class_id: int, page: int, size: int = 30, keyword: str | None = None) -> dict:
        from sqlmodel import or_
        filters = [Student.class_id == class_id]
        if keyword:
            like_pattern = f"%{keyword}%"
            filters.append(or_(Student.id.like(like_pattern), Student.username.like(like_pattern)))
        rows, total = await paginate(self.session, Student, page, size, filters=filters, order_col=Student.id)
        result_list = [
            {
                "id": s.id,
                "username": s.username,
                "class_id": s.class_id,
                "organization_id": s.organization_id,
            }
            for s in rows
        ]
        return {"list": result_list, "total": total}

    async def get_classes_by_organization(self, organization_id: int) -> list[dict]:
        stmt = select(StudentClass).where(StudentClass.organization_id == organization_id)
        classes = (await self.session.exec(stmt)).all()
        return [ClassRead.model_validate(c).model_dump(mode='json') for c in classes]

    async def get_all_classes(self) -> list[dict]:
        stmt = select(StudentClass)
        classes = (await self.session.exec(stmt)).all()
        return [ClassRead.model_validate(c).model_dump(mode='json') for c in classes]

    async def get_teacher_org_id(self, teacher_id: str) -> int | None:
        stmt = select(Teacher.organization_id).where(Teacher.id == teacher_id)
        result = (await self.session.exec(stmt)).first()
        return result

    async def get_gai_task_students(self, course_id, task_id: int, teacher_id: str) -> list[dict]:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权查看此课程")
        stmt = select(AnalysisTask).where(AnalysisTask.analysis_task_id == task_id)
        task = (await self.session.exec(stmt)).one_or_none()
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")

        stmt = select(CourseRegistrationRecord.student_id).where(
            CourseRegistrationRecord.course_id == course_id
        )
        student_ids = list((await self.session.exec(stmt)).all())
        if not student_ids:
            return []

        stmt = select(Student).where(Student.id.in_(student_ids))
        student_records = (await self.session.exec(stmt)).all()
        class_ids = [s.class_id for s in student_records if s.class_id]
        if class_ids:
            stmt = select(StudentClass).where(StudentClass.class_id.in_(class_ids))
            classes = (await self.session.exec(stmt)).all()
        else:
            classes = []
        class_map = {c.class_id: c.class_name for c in classes}
        students = [(s.id, s.username, class_map.get(s.class_id, "") or "未分配班级") for s in student_records]

        student_id_list = [s_id for s_id, _, _ in students]
        stmt = select(AnalysisTaskCompletion.student_id).where(
            AnalysisTaskCompletion.course_id == course_id,
            AnalysisTaskCompletion.analysis_task_id == task_id,
        )
        completed_set = set((await self.session.exec(stmt)).all())
        completed_set = completed_set & set(student_id_list)

        return [
            {"id": s_id, "name": s_name, "class_name": c_name, "is_completed": s_id in completed_set}
            for s_id, s_name, c_name in students
        ]
