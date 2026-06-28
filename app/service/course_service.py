import uuid

from sqlalchemy.orm import selectinload
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.common.formatters import _validate_task_payload_consistency
from app.common.tools import is_deletable_resource_path, remove_file, to_upload_relative_path
from app.core.database import db
from app.core.exceptions import AppBusinessException
from app.model.models import (
    AnalysisDescription,
    AnalysisTask,
    AnalysisTaskCompletion,
    Chapter,
    Course,
    CourseRegistrationRecord,
    Section,
    SectionCompletionRecord,
    Student,
    StudentClass,
    Task,
    TaskCompletion,
    Teacher,
)
from app.schema.chapter import ChapterBatchPayload
from app.schema.course import CourseDetailRead, CourseInfo, CourseRead
from app.util.time_util import format_utc_time
from fastapi import Depends


class CourseService:
    """课程管理 (封面+章节+注册)"""

    def __init__(self, session: AsyncSession = Depends(db.get_session)):
        self.session = session

    async def create_course_with_students(self, course_info: CourseInfo, class_names: list[str]) -> uuid.UUID:
        course = Course(
            course_name=course_info.course_name,
            teacher_id=course_info.teacher_id,
            course_cover=course_info.course_cover,
            teaching_plan=course_info.teaching_plan,
            invited_code=course_info.invited_code,
            is_invitation_valid=course_info.is_invitation_valid,
        )
        self.session.add(course)
        await self.session.flush()
        await self.session.refresh(course)

        if class_names:
            stmt = select(StudentClass).where(StudentClass.class_name.in_(class_names))
            classes = (await self.session.exec(stmt)).all()
            if classes:
                class_ids = [c.class_id for c in classes]
                stmt = select(Student.id).where(Student.class_id.in_(class_ids))
                student_ids = list((await self.session.exec(stmt)).all())
                if student_ids:
                    self.session.add_all(
                        [CourseRegistrationRecord(student_id=sid, course_id=course.course_id) for sid in student_ids]
                    )
                    await self.session.flush()
        return course.course_id

    async def delete_course(self, teacher_id: str, course_id: uuid.UUID) -> None:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course:
            raise AppBusinessException(404, "课程不存在")
        if course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权删除此课程")

        cover_to_remove = (
            course.course_cover if course.course_cover and course.course_cover != "covers/default.png" else None
        )
        stmt = select(Chapter).where(Chapter.course_id == course_id).order_by(Chapter.chapter_order)
        chapters = (await self.session.exec(stmt)).all()
        section_paths = []
        if chapters:
            chapter_ids = [ch.chapter_id for ch in chapters]
            stmt = select(Section).where(Section.chapter_id.in_(chapter_ids))
            sections = (await self.session.exec(stmt)).all()
            section_paths = [s.resource_path for s in sections if s.resource_path]

        await self.session.delete(course)
        await self.session.flush()

        if cover_to_remove:
            await remove_file(cover_to_remove)

        if section_paths:
            safe_paths = {p for p in section_paths if p and is_deletable_resource_path(p)}
            if safe_paths:
                stmt = select(Section.resource_path).where(Section.resource_path.in_(safe_paths))
                referenced = set((await self.session.exec(stmt)).all())
                orphaned = safe_paths - referenced
                for path in orphaned:
                    await remove_file(to_upload_relative_path(path))

    async def patch_course(self, course_id: uuid.UUID, teacher_id: str, update_data: dict) -> dict:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course:
            raise AppBusinessException(404, "课程不存在")
        if course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权修改此课程")
        valid_updates = {k: v for k, v in update_data.items() if v is not None}
        for key, value in valid_updates.items():
            if hasattr(course, key):
                setattr(course, key, value)
        self.session.add(course)
        await self.session.flush()
        await self.session.refresh(course)
        return {
            "course_id": str(course.course_id),
            "course_name": course.course_name,
            "course_cover": course.course_cover,
            "teaching_plan": course.teaching_plan,
            "invited_code": course.invited_code,
            "is_invitation_valid": course.is_invitation_valid,
        }

    async def join_course_by_code(self, student_id: str, invite_code: str) -> str:
        stmt = select(Course).where(Course.invited_code == invite_code)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course:
            raise AppBusinessException(404, "课程不存在或邀请码错误")
        if not course.is_invitation_valid:
            raise AppBusinessException(400, "该课程的邀请码已失效")
        stmt = select(CourseRegistrationRecord).where(
            CourseRegistrationRecord.student_id == student_id,
            CourseRegistrationRecord.course_id == course.course_id,
        )
        if (await self.session.exec(stmt)).first():
            raise AppBusinessException(400, "你已经加入了该课程")
        self.session.add(CourseRegistrationRecord(student_id=student_id, course_id=course.course_id))
        await self.session.flush()
        return str(course.course_id)

    async def batch_update_chapters(
        self, course_id: uuid.UUID, payload: ChapterBatchPayload, teacher_id: str
    ) -> list[dict]:
        from sqlalchemy.exc import IntegrityError

        removed_resource_paths: set[str] = set()

        try:
            stmt = select(Course).where(Course.course_id == course_id)
            course = (await self.session.exec(stmt)).one_or_none()
            if not course:
                raise AppBusinessException(404, "课程不存在")
            if course.teacher_id != teacher_id:
                raise AppBusinessException(403, "无权修改此课程")

            req_chapter_ids = {ch.chapter_id for ch in payload.chapters if ch.chapter_id is not None}
            stmt = select(Chapter).where(Chapter.course_id == course_id).order_by(Chapter.chapter_order)
            db_chapters = (await self.session.exec(stmt)).all()
            to_delete_ch_ids = [ch.chapter_id for ch in db_chapters if ch.chapter_id not in req_chapter_ids]

            if to_delete_ch_ids:
                stmt = select(Section.resource_path).where(Section.chapter_id.in_(to_delete_ch_ids))
                removed_paths = list((await self.session.exec(stmt)).all())
                removed_resource_paths.update({p for p in removed_paths if p})
                from sqlmodel import delete as _sql_delete

                await self.session.execute(_sql_delete(Chapter).where(Chapter.chapter_id.in_(to_delete_ch_ids)))

            stmt = select(Chapter).where(Chapter.course_id == course_id).order_by(Chapter.chapter_order)
            remaining = (await self.session.exec(stmt)).all()
            temp_order = -1
            for ch in remaining:
                ch.chapter_order = temp_order
                temp_order -= 1
                self.session.add(ch)
            await self.session.flush()

            new_chapter_objs = []
            for ch_data in payload.chapters:
                current_real_ch_id = ch_data.chapter_id
                if ch_data.chapter_id is None:
                    new_ch = Chapter(course_id=course_id, chapter_title=ch_data.chapter_title, chapter_order=temp_order)
                    self.session.add(new_ch)
                    await self.session.flush()
                    await self.session.refresh(new_ch)
                    current_real_ch_id = new_ch.chapter_id
                    new_chapter_objs.append((ch_data, new_ch))
                    temp_order -= 1
                else:
                    stmt = select(Chapter).where(Chapter.chapter_id == current_real_ch_id)
                    db_ch = (await self.session.exec(stmt)).one_or_none()
                    if not db_ch:
                        raise AppBusinessException(404, "章节不存在")
                    if db_ch.course_id != course_id:
                        raise AppBusinessException(403, "无权修改此章节")
                    db_ch.chapter_title = ch_data.chapter_title
                    self.session.add(db_ch)
                    await self.session.flush()

                req_sec_ids = {s.section_id for s in ch_data.sub_tasks if s.section_id is not None}
                stmt = select(Section).where(Section.chapter_id == current_real_ch_id).order_by(Section.section_order)
                db_secs = (await self.session.exec(stmt)).all()
                del_sec_ids = [s.section_id for s in db_secs if s.section_id not in req_sec_ids]

                if del_sec_ids:
                    stmt = select(Section.resource_path).where(Section.chapter_id.in_(del_sec_ids))
                    removed_paths = list((await self.session.exec(stmt)).all())
                    removed_resource_paths.update({p for p in removed_paths if p})
                    from sqlmodel import delete as _sql_delete

                    await self.session.execute(_sql_delete(Section).where(Section.section_id.in_(del_sec_ids)))

                stmt = select(Section).where(Section.chapter_id == current_real_ch_id).order_by(Section.section_order)
                remaining_secs = (await self.session.exec(stmt)).all()
                temp_sec_order = -1
                for sec in remaining_secs:
                    sec.section_order = temp_sec_order
                    temp_sec_order -= 1
                    self.session.add(sec)
                await self.session.flush()

                section_objs = []
                for st_data in ch_data.sub_tasks:
                    if st_data.section_id is None:
                        if not st_data.resource_path:
                            raise AppBusinessException(400, "子任务资源不能为空，请先上传资源文件")
                        new_sec = Section(
                            section_title=st_data.section_title,
                            section_type=st_data.section_type,
                            resource_path=st_data.resource_path,
                            description=st_data.description,
                            chapter_id=current_real_ch_id,
                            section_order=temp_sec_order,
                        )
                        self.session.add(new_sec)
                        await self.session.flush()
                        await self.session.refresh(new_sec)
                        section_objs.append(new_sec)
                        temp_sec_order -= 1
                    else:
                        stmt = select(Section).where(Section.section_id == st_data.section_id)
                        db_sec = (await self.session.exec(stmt)).one_or_none()
                        if not db_sec:
                            raise AppBusinessException(404, "子任务不存在")
                        if db_sec.chapter_id != current_real_ch_id:
                            raise AppBusinessException(403, "无权修改此子任务")
                        if not st_data.resource_path:
                            raise AppBusinessException(400, "子任务资源不能为空，请先上传资源文件")
                        if db_sec.resource_path and db_sec.resource_path != st_data.resource_path:
                            removed_resource_paths.add(db_sec.resource_path)
                        db_sec.section_title = st_data.section_title
                        db_sec.section_type = st_data.section_type
                        db_sec.resource_path = st_data.resource_path
                        db_sec.description = st_data.description
                        section_objs.append(db_sec)

                for idx, sec_obj in enumerate(section_objs):
                    sec_obj.section_order = idx + 1
                    self.session.add(sec_obj)
                await self.session.flush()

            for idx, ch_data in enumerate(payload.chapters):
                target_id = ch_data.chapter_id
                if target_id is None:
                    for p_data, ch_obj in new_chapter_objs:
                        if p_data is ch_data:
                            target_id = ch_obj.chapter_id
                            break
                if target_id:
                    stmt = select(Chapter).where(Chapter.chapter_id == target_id)
                    db_ch = (await self.session.exec(stmt)).one_or_none()
                    if db_ch:
                        db_ch.chapter_order = ch_data.chapter_order if ch_data.chapter_order is not None else idx + 1
                        self.session.add(db_ch)
            await self.session.flush()

            stmt = select(Chapter).where(Chapter.course_id == course_id).order_by(Chapter.chapter_order)
            final_chapters = (await self.session.exec(stmt)).all()
            result = []
            for ch in final_chapters:
                stmt = select(Section).where(Section.chapter_id == ch.chapter_id).order_by(Section.section_order)
                secs = (await self.session.exec(stmt)).all()
                result.append(
                    {
                        "chapter_id": ch.chapter_id,
                        "chapter_title": ch.chapter_title,
                        "chapter_order": ch.chapter_order,
                        "sub_tasks": [
                            {
                                "section_id": s.section_id,
                                "section_title": s.section_title,
                                "section_type": s.section_type.value,
                                "resource_path": s.resource_path,
                                "description": s.description,
                                "section_order": s.section_order,
                            }
                            for s in secs
                        ],
                    }
                )

            safe_removed = {p for p in removed_resource_paths if p and is_deletable_resource_path(p)}
            if safe_removed:
                stmt = select(Section.resource_path).where(Section.resource_path.in_(safe_removed))
                referenced = set((await self.session.exec(stmt)).all())
                orphaned = safe_removed - referenced
                for path in orphaned:
                    await remove_file(to_upload_relative_path(path))
            return result

        except AppBusinessException:
            raise
        except IntegrityError:
            raise AppBusinessException(400, "章节或子任务顺序冲突，请刷新后重试")

    async def create_task(self, course_id: uuid.UUID, teacher_id: str, task_data: dict) -> dict:
        quiz_data = task_data.get("quiz", [])
        answer_data = task_data.get("answer", [])
        _validate_task_payload_consistency(quiz_data, answer_data)

        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权操作此课程")

        new_task = Task(
            course_id=course_id,
            task_title=task_data["task_title"],
            quiz=quiz_data,
            answer=answer_data,
            deadline=task_data.get("deadline"),
        )
        self.session.add(new_task)
        await self.session.flush()
        await self.session.refresh(new_task)
        return {
            "task_id": new_task.task_id,
            "task_title": new_task.task_title,
            "type": "quiz",
            "quiz": new_task.quiz,
            "answer": new_task.answer,
            "deadline": format_utc_time(new_task.deadline),
        }

    async def update_task(self, course_id: uuid.UUID, task_id: int, teacher_id: str, task_data: dict) -> dict:
        quiz_data = task_data.get("quiz", [])
        answer_data = task_data.get("answer", [])
        _validate_task_payload_consistency(quiz_data, answer_data)

        stmt = select(Task).where(Task.task_id == task_id)
        task = (await self.session.exec(stmt)).one_or_none()
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")

        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权操作此课程")

        task.task_title = task_data["task_title"]
        task.quiz = quiz_data
        task.answer = answer_data
        task.deadline = task_data.get("deadline")
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return {
            "task_id": task.task_id,
            "task_title": task.task_title,
            "type": "quiz",
            "quiz": task.quiz,
            "answer": task.answer,
            "deadline": format_utc_time(task.deadline),
        }

    async def delete_task(self, course_id: uuid.UUID, task_id: int, teacher_id: str) -> None:
        stmt = select(Task).where(Task.task_id == task_id)
        task = (await self.session.exec(stmt)).one_or_none()
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")

        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权操作此课程")

        await self.session.delete(task)
        await self.session.flush()

    async def create_gai_task(self, course_id: uuid.UUID, teacher_id: str, task_data: dict) -> dict:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权操作此课程")

        new_task = AnalysisTask(course_id=course_id, **task_data)
        self.session.add(new_task)
        await self.session.flush()
        await self.session.refresh(new_task)
        return {
            "analysis_task_id": new_task.analysis_task_id,
            "analysis_task_title": new_task.analysis_task_title,
            "task_description": new_task.task_description,
            "analysis_description": new_task.analysis_description,
            "evaluation_criterion": new_task.evaluation_criterion,
            "deadline": format_utc_time(new_task.deadline),
        }

    async def update_gai_task(self, course_id: uuid.UUID, task_id: int, teacher_id: str, task_data: dict) -> dict:
        stmt = select(AnalysisTask).where(AnalysisTask.analysis_task_id == task_id)
        task = (await self.session.exec(stmt)).one_or_none()
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")

        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权操作此课程")

        for key, value in task_data.items():
            setattr(task, key, value)
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return {
            "analysis_task_id": task.analysis_task_id,
            "analysis_task_title": task.analysis_task_title,
            "task_description": task.task_description,
            "analysis_description": task.analysis_description,
            "evaluation_criterion": task.evaluation_criterion,
            "deadline": format_utc_time(task.deadline),
        }

    async def delete_gai_task(self, course_id: uuid.UUID, task_id: int, teacher_id: str) -> None:
        stmt = select(AnalysisTask).where(AnalysisTask.analysis_task_id == task_id)
        task = (await self.session.exec(stmt)).one_or_none()
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")

        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权操作此课程")

        await self.session.delete(task)
        await self.session.flush()

    async def get_teacher_courses_page(self, teacher_id: str, page: int, size: int = 16) -> list[dict]:
        offset = (page - 1) * size
        stmt = (
            select(Course).where(Course.teacher_id == teacher_id).order_by(Course.course_id).offset(offset).limit(size)
        )
        courses = (await self.session.exec(stmt)).all()
        return [CourseRead.model_validate(c).model_dump(mode="json") for c in courses]

    async def get_course_detail(self, course_id: uuid.UUID, teacher_id: str) -> dict:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course:
            raise AppBusinessException(404, "课程不存在")
        if course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权查看此课程")
        return CourseDetailRead.model_validate(course).model_dump(mode="json")

    async def get_course_detail_for_student(self, course_id: uuid.UUID, student_id: str) -> dict:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course:
            raise AppBusinessException(404, "课程不存在")
        stmt = select(CourseRegistrationRecord).where(
            CourseRegistrationRecord.student_id == student_id,
            CourseRegistrationRecord.course_id == course_id,
        )
        if not (await self.session.exec(stmt)).first():
            raise AppBusinessException(403, "无权访问此课程")
        stmt = select(Course.teacher_id).where(Course.course_id == course_id)
        teacher_id = (await self.session.exec(stmt)).first()
        teacher_name = ""
        if teacher_id:
            stmt = select(Teacher.username).where(Teacher.id == teacher_id)
            teacher_name = (await self.session.exec(stmt)).first() or ""
        return {
            "course_id": str(course.course_id),
            "course_name": course.course_name,
            "course_cover": course.course_cover,
            "teacher_name": teacher_name or "",
        }

    async def get_chapters_with_sections(
        self,
        course_id: uuid.UUID,
        student_id: str | None = None,
        teacher_id: str | None = None,
    ) -> list[dict]:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course:
            raise AppBusinessException(404, "课程不存在")
        if student_id:
            stmt = select(CourseRegistrationRecord).where(
                CourseRegistrationRecord.student_id == student_id,
                CourseRegistrationRecord.course_id == course_id,
            )
            if not (await self.session.exec(stmt)).first():
                raise AppBusinessException(403, "无权访问此课程")
        elif teacher_id and course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权访问此课程")

        stmt = (
            select(Chapter)
            .where(Chapter.course_id == course_id)
            .options(selectinload(Chapter.sections))
            .order_by(Chapter.chapter_order)
        )
        chapters = list((await self.session.exec(stmt)).all())
        if not chapters:
            return []

        completions, learning_effects = set(), {}
        if student_id:
            all_section_ids = [s.section_id for ch in chapters for s in ch.sections]
            if all_section_ids:
                stmt = select(SectionCompletionRecord).where(
                    SectionCompletionRecord.student_id == student_id,
                    SectionCompletionRecord.section_id.in_(all_section_ids),
                )
                records = (await self.session.exec(stmt)).all()
                completions_dict = {r.section_id: r.learning_effect for r in records}
                completions = set(completions_dict.keys())
                learning_effects = completions_dict

        result = []
        for ch in chapters:
            sub_tasks = []
            for s in sorted(ch.sections, key=lambda x: x.section_order):
                task_data = {
                    "section_id": s.section_id,
                    "section_title": s.section_title,
                    "section_type": s.section_type.value,
                    "resource_path": s.resource_path,
                    "description": s.description,
                    "section_order": s.section_order,
                }
                if student_id is not None:
                    task_data["is_completed"] = s.section_id in completions
                    task_data["learning_effect"] = learning_effects.get(s.section_id, 0)
                sub_tasks.append(task_data)
            result.append(
                {
                    "chapter_id": ch.chapter_id,
                    "chapter_title": ch.chapter_title,
                    "chapter_order": ch.chapter_order,
                    "sub_tasks": sub_tasks,
                }
            )
        return result

    async def get_student_courses_page(self, student_id: str, page: int) -> dict:
        size = 16
        count_stmt = (
            select(func.count())
            .select_from(CourseRegistrationRecord)
            .where(CourseRegistrationRecord.student_id == student_id)
        )
        total = (await self.session.exec(count_stmt)).one()
        offset = (page - 1) * size
        stmt = (
            select(CourseRegistrationRecord.course_id)
            .where(CourseRegistrationRecord.student_id == student_id)
            .order_by(CourseRegistrationRecord.course_id.desc())
            .offset(offset)
            .limit(size + 1)
        )
        course_ids = list((await self.session.exec(stmt)).all())
        has_more = len(course_ids) > size
        if has_more:
            course_ids = course_ids[:size]
        courses = []
        for cid in course_ids:
            stmt = select(Course).where(Course.course_id == cid)
            course = (await self.session.exec(stmt)).one_or_none()
            if not course:
                continue
            stmt = select(Teacher.username).where(Teacher.id == course.teacher_id)
            teacher_name = (await self.session.exec(stmt)).first() or ""
            course_id = str(course.course_id)
            courses.append(
                {
                    "course_id": course_id,
                    "course_name": course.course_name,
                    "teacher_name": teacher_name,
                    "course_cover": course.course_cover,
                    "id": course_id,
                    "name": course.course_name,
                    "teacher": teacher_name,
                }
            )
        return {"courses": courses, "has_more": has_more}

    async def _get_students_with_class(self, course_id: uuid.UUID) -> list[tuple[str, str, str]]:
        stmt = select(CourseRegistrationRecord.student_id).where(CourseRegistrationRecord.course_id == course_id)
        student_ids = list((await self.session.exec(stmt)).all())
        if not student_ids:
            return []
        stmt = select(Student).where(Student.id.in_(student_ids))
        students = list((await self.session.exec(stmt)).all())
        class_ids = [s.class_id for s in students if s.class_id]
        if class_ids:
            stmt = select(StudentClass).where(StudentClass.class_id.in_(class_ids))
            classes = list((await self.session.exec(stmt)).all())
        else:
            classes = []
        class_map = {c.class_id: c.class_name for c in classes}
        return [(s.id, s.username, class_map.get(s.class_id, "") or "未分配班级") for s in students]

    async def get_course_students(self, course_id: uuid.UUID, teacher_id: str) -> list[dict]:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权查看此课程")
        students = await self._get_students_with_class(course_id)
        return [{"id": s_id, "name": s_name, "class_name": c_name} for s_id, s_name, c_name in students]

    async def get_completion_details(
        self, course_id: uuid.UUID, record_type: str, target_id: int, teacher_id: str
    ) -> list[dict]:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权查看此课程")

        if record_type == "section":
            stmt = select(Section).where(Section.section_id == target_id)
            section = (await self.session.exec(stmt)).one_or_none()
            if not section:
                raise AppBusinessException(404, "目标资源不存在")
            stmt = select(Chapter).where(Chapter.chapter_id == section.chapter_id)
            chapter = (await self.session.exec(stmt)).one_or_none()
            if not chapter or chapter.course_id != course_id:
                raise AppBusinessException(404, "目标资源不存在")
        elif record_type == "task":
            stmt = select(Task).where(Task.task_id == target_id)
            task = (await self.session.exec(stmt)).one_or_none()
            if not task or task.course_id != course_id:
                raise AppBusinessException(404, "目标资源不存在")
        else:
            raise AppBusinessException(400, "type 参数错误")

        students = await self._get_students_with_class(course_id)
        student_map = {
            s_id: {"name": s_name, "class_name": c_name or "未分配班级"} for s_id, s_name, c_name in students
        }

        completion_map = {}
        if record_type == "section":
            stmt = select(SectionCompletionRecord).where(SectionCompletionRecord.section_id == target_id)
            records = (await self.session.exec(stmt)).all()
            for rec in records:
                completion_map[rec.student_id] = float(rec.learning_effect) if rec.learning_effect is not None else 0
        else:
            stmt = select(TaskCompletion).where(TaskCompletion.task_id == target_id)
            records = (await self.session.exec(stmt)).all()
            for rec in records:
                completion_map[rec.student_id] = rec.task_scores if rec.task_scores is not None else 0

        return [
            {
                "student_name": info["name"],
                "class_name": info["class_name"],
                "is_completed": s_id in completion_map,
                "score": completion_map.get(s_id, 0),
            }
            for s_id, info in student_map.items()
        ]

    async def get_course_raw_records(self, course_id: uuid.UUID, teacher_id: str) -> list[dict]:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权查看此课程")

        stmt = select(CourseRegistrationRecord.student_id).where(CourseRegistrationRecord.course_id == course_id)
        student_ids = list((await self.session.exec(stmt)).all())
        if not student_ids:
            return []

        records_map = {
            sid: {
                "student_id": sid,
                "done_section_ids": set(),
                "done_task_ids": set(),
                "done_gai_ids": set(),
                "task_scores": {},
            }
            for sid in student_ids
        }

        stmt = select(Chapter).where(Chapter.course_id == course_id).order_by(Chapter.chapter_order)
        chapters = list((await self.session.exec(stmt)).all())
        section_ids = []
        if chapters:
            chapter_ids = [ch.chapter_id for ch in chapters]
            stmt = select(Section).where(Section.chapter_id.in_(chapter_ids))
            sections = (await self.session.exec(stmt)).all()
            section_ids = [s.section_id for s in sections]
        stmt = select(Task.task_id).where(Task.course_id == course_id)
        task_ids = list((await self.session.exec(stmt)).all())

        if section_ids:
            stmt = select(SectionCompletionRecord.student_id, SectionCompletionRecord.section_id).where(
                SectionCompletionRecord.student_id.in_(student_ids),
                SectionCompletionRecord.section_id.in_(section_ids),
            )
            for sid, section_id in (await self.session.exec(stmt)).all():
                if sid in records_map:
                    records_map[sid]["done_section_ids"].add(section_id)

        if task_ids:
            stmt = select(TaskCompletion.student_id, TaskCompletion.task_id, TaskCompletion.task_scores).where(
                TaskCompletion.student_id.in_(student_ids),
                TaskCompletion.task_id.in_(task_ids),
            )
            for sid, tid, task_score in (await self.session.exec(stmt)).all():
                if sid in records_map:
                    records_map[sid]["done_task_ids"].add(tid)
                    records_map[sid]["task_scores"][str(tid)] = task_score

        stmt = select(AnalysisTaskCompletion.student_id, AnalysisTaskCompletion.analysis_task_id).where(
            AnalysisTaskCompletion.course_id == course_id,
            AnalysisTaskCompletion.student_id.in_(student_ids),
        )
        for sid, analysis_task_id in (await self.session.exec(stmt)).all():
            if sid in records_map:
                records_map[sid]["done_gai_ids"].add(analysis_task_id)

        return [
            {
                "student_id": item["student_id"],
                "done_section_ids": sorted(item["done_section_ids"]),
                "done_task_ids": sorted(item["done_task_ids"]),
                "done_gai_ids": sorted(item["done_gai_ids"]),
                "task_scores": item["task_scores"],
            }
            for item in records_map.values()
        ]

    async def get_course_ai_text(self, course_id: uuid.UUID, teacher_id: str, student_id: str = "all") -> str:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权查看此课程")

        if student_id == "all":
            return course.teaching_analysis if course.teaching_analysis else "暂无全班综合 AI 分析数据。"

        stmt = select(CourseRegistrationRecord).where(
            CourseRegistrationRecord.student_id == student_id,
            CourseRegistrationRecord.course_id == course_id,
        )
        if not (await self.session.exec(stmt)).first():
            raise AppBusinessException(404, "学生不在该课程中")

        stmt = (
            select(AnalysisDescription.analysis_content)
            .where(
                AnalysisDescription.student_id == student_id,
                AnalysisDescription.course_id == course_id,
            )
            .order_by(AnalysisDescription.analysis_id.desc())
        )
        record = (await self.session.exec(stmt)).first()
        return record if record else "暂无该学生的 AI 分析数据。"

    async def get_course_full_context(self, course_id: uuid.UUID) -> dict | None:
        course = await self.session.get(Course, course_id)
        if not course:
            return None

        students = (
            await self.session.exec(
                select(Student.id, Student.username)
                .join(CourseRegistrationRecord, Student.id == CourseRegistrationRecord.student_id)
                .where(CourseRegistrationRecord.course_id == course_id)
            )
        ).all()
        if not students:
            return None

        student_map = {s_id: s_name for s_id, s_name in students}

        chapters_data = []
        chapters = (
            await self.session.exec(
                select(Chapter).where(Chapter.course_id == course_id).order_by(Chapter.chapter_order)
            )
        ).all()

        for ch in chapters:
            sections = (
                await self.session.exec(
                    select(Section).where(Section.chapter_id == ch.chapter_id).order_by(Section.section_order)
                )
            ).all()

            sections_data = []
            for sec in sections:
                completions = (
                    await self.session.exec(
                        select(SectionCompletionRecord).where(SectionCompletionRecord.section_id == sec.section_id)
                    )
                ).all()

                sec_stats = []
                for comp in completions:
                    sec_stats.append(
                        {
                            "student_id": comp.student_id,
                            "student_name": student_map.get(comp.student_id, "未知学生"),
                            "is_completed": True,
                            "learning_effect": comp.learning_effect,
                        }
                    )

                sections_data.append(
                    {
                        "section_id": sec.section_id,
                        "section_title": sec.section_title,
                        "description": sec.description,
                        "student_stats": sec_stats,
                    }
                )

            chapters_data.append(
                {
                    "chapter_id": ch.chapter_id,
                    "chapter_title": ch.chapter_title,
                    "sections": sections_data,
                }
            )

        tasks_data = []
        tasks = (await self.session.exec(select(Task).where(Task.course_id == course_id))).all()

        for task in tasks:
            completions = (
                await self.session.exec(select(TaskCompletion).where(TaskCompletion.task_id == task.task_id))
            ).all()

            stu_completions_data = []
            for comp in completions:
                stu_completions_data.append(
                    {
                        "student_id": comp.student_id,
                        "student_name": student_map.get(comp.student_id, "未知学生"),
                        "answers": comp.answer,
                        "score": comp.task_scores,
                    }
                )

            tasks_data.append(
                {
                    "task_id": task.task_id,
                    "task_title": task.task_title,
                    "quiz": task.quiz,
                    "answer": task.answer,
                    "student_completions": stu_completions_data,
                }
            )

        return {
            "course_name": course.course_name,
            "teaching_plan": course.teaching_plan,
            "chapters": chapters_data,
            "tasks": tasks_data,
        }

    async def update_teaching_analysis(self, course_id: uuid.UUID, analysis_text: str) -> None:
        course = await self.session.get(Course, course_id)
        if course:
            course.teaching_analysis = analysis_text
            self.session.add(course)
            await self.session.commit()
