from datetime import UTC, datetime

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import AppBusinessException
from app.core.database import get_session
from app.model.models import (
    AnalysisTask,
    AnalysisTaskCompletion,
    Chapter,
    Course,
    CourseRegistrationRecord,
    Section,
    SectionCompletionRecord,
    Student,
    StudentClass,
    StudentDailyStudyTimeInCourse,
    Task,
    TaskCompletion,
    Teacher,
)
from app.util.time_util import format_utc_time
from fastapi import Depends


class StudentService:
    """学生端: 学习进度、统计"""

    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session

    async def get_weekly_study(self, student_id: str) -> list[int]:
        stmt = select(StudentDailyStudyTimeInCourse).where(StudentDailyStudyTimeInCourse.student_id == student_id)
        records = (await self.session.exec(stmt)).all()
        totals = [0] * 7
        for record in records:
            data = record.study_data
            if not data:
                continue
            for idx in range(min(len(data), 7)):
                value = data[idx]
                totals[idx] += int(value) if value else 0
        return totals

    async def get_weekly_study_in_course(self, student_id: str, course_id, teacher_id: str) -> list[float]:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course:
            raise AppBusinessException(404, "课程不存在")
        if course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权查看此课程数据")
        stmt = select(StudentDailyStudyTimeInCourse).where(
            StudentDailyStudyTimeInCourse.student_id == student_id,
            StudentDailyStudyTimeInCourse.course_id == course_id,
        )
        records = (await self.session.exec(stmt)).all()
        totals = [0.0] * 7
        for record in records:
            data = record.study_data
            if not data:
                continue
            for idx in range(min(len(data), 7)):
                value = data[idx]
                totals[idx] += int(value) if value else 0
        return totals

    async def get_tasks_todo(self, student_id: str) -> dict:
        current_time = datetime.now(UTC)

        stmt = select(CourseRegistrationRecord.course_id).where(CourseRegistrationRecord.student_id == student_id)
        course_ids = list((await self.session.exec(stmt)).all())
        if not course_ids:
            return {"tasks": [], "gai_tasks": []}

        stmt = select(TaskCompletion.task_id).where(TaskCompletion.student_id == student_id)
        completed_task_ids_set = set((await self.session.exec(stmt)).all())

        todo_tasks = []
        for course_id in course_ids:
            stmt = select(Task).where(Task.course_id == course_id)
            tasks = (await self.session.exec(stmt)).all()
            for task in tasks:
                if task.task_id in completed_task_ids_set:
                    continue
                if task.deadline and task.deadline < current_time:
                    continue
                stmt = select(Course).where(Course.course_id == course_id)
                course = (await self.session.exec(stmt)).one_or_none()
                todo_tasks.append(
                    {
                        "task_id": str(task.task_id),
                        "task_title": task.task_title,
                        "course_name": course.course_name if course else "",
                        "course_id": str(course_id),
                        "is_completed": False,
                        "deadline": format_utc_time(task.deadline),
                    }
                )

        stmt = select(AnalysisTaskCompletion.analysis_task_id).where(AnalysisTaskCompletion.student_id == student_id)
        completed_gai_ids_set = set((await self.session.exec(stmt)).all())

        todo_gai_tasks = []
        for course_id in course_ids:
            stmt = select(AnalysisTask).where(AnalysisTask.course_id == course_id)
            gai_tasks = (await self.session.exec(stmt)).all()
            for task in gai_tasks:
                if task.analysis_task_id in completed_gai_ids_set:
                    continue
                if task.deadline and task.deadline < current_time:
                    continue
                stmt = select(Course).where(Course.course_id == course_id)
                course = (await self.session.exec(stmt)).one_or_none()
                todo_gai_tasks.append(
                    {
                        "task_id": str(task.analysis_task_id),
                        "task_title": task.analysis_task_title,
                        "course_name": course.course_name if course else "",
                        "course_id": str(course_id),
                        "is_completed": False,
                        "deadline": format_utc_time(task.deadline),
                    }
                )

        return {"tasks": todo_tasks, "gai_tasks": todo_gai_tasks}

    async def report_study_duration(self, course_id, student_id: str, duration: int) -> None:
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

        weekday_idx = datetime.now(UTC).weekday()
        stmt = (
            select(StudentDailyStudyTimeInCourse)
            .where(
                StudentDailyStudyTimeInCourse.student_id == student_id,
                StudentDailyStudyTimeInCourse.course_id == course_id,
            )
            .with_for_update()
        )
        record = (await self.session.exec(stmt)).one_or_none()
        if not record:
            study_data = [0] * 7
            study_data[weekday_idx] = int(duration)
            self.session.add(
                StudentDailyStudyTimeInCourse(student_id=student_id, course_id=course_id, study_data=study_data)
            )
        else:
            current_data = record.study_data
            if not isinstance(current_data, list) or len(current_data) != 7:
                current_data = [0] * 7
            original_val = current_data[weekday_idx]
            current_data[weekday_idx] = (int(original_val) if original_val else 0) + int(duration)
            record.study_data = current_data
            flag_modified(record, "study_data")
            self.session.add(record)
        await self.session.flush()

    async def get_section_detail(self, course_id, section_id: int, student_id: str) -> dict:
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

        stmt = select(Section).where(Section.section_id == section_id)
        section = (await self.session.exec(stmt)).one_or_none()
        if not section:
            raise AppBusinessException(404, "小节不存在")

        stmt = select(Chapter).where(Chapter.chapter_id == section.chapter_id)
        chapter = (await self.session.exec(stmt)).one_or_none()
        if not chapter or chapter.course_id != course_id:
            raise AppBusinessException(404, "小节不存在")

        stmt = select(SectionCompletionRecord).where(
            SectionCompletionRecord.section_id == section_id,
            SectionCompletionRecord.student_id == student_id,
        )
        completion = (await self.session.exec(stmt)).one_or_none()

        return {
            "chapter_name": chapter.chapter_title or "",
            "section_title": section.section_title,
            "resource_type": section.section_type.value,
            "resource_url": section.resource_path,
            "description": section.description,
            "is_completed": completion is not None,
        }

    async def get_course_detail_for_student(self, course_id, student_id: str) -> dict:
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
            "teacher_name": teacher_name,
        }

    async def get_student_class_info(self, student_id: str) -> dict | None:
        stmt = select(Student).where(Student.id == student_id)
        student = (await self.session.exec(stmt)).one_or_none()
        if not student:
            return None
        stmt = select(StudentClass).where(StudentClass.class_id == student.class_id)
        class_obj = (await self.session.exec(stmt)).one_or_none()
        return {
            "student_id": student.id,
            "username": student.username,
            "class_id": student.class_id,
            "class_name": class_obj.class_name if class_obj else "",
            "organization_id": student.organization_id,
        }

    async def get_student_courses_with_progress(self, student_id: str) -> list[dict]:
        stmt = (
            select(CourseRegistrationRecord.course_id)
            .where(CourseRegistrationRecord.student_id == student_id)
            .order_by(CourseRegistrationRecord.course_id.desc())
        )
        course_ids = list((await self.session.exec(stmt)).all())

        courses = []
        for cid in course_ids:
            stmt = select(Course).where(Course.course_id == cid)
            course = (await self.session.exec(stmt)).one_or_none()
            if not course:
                continue

            stmt = select(Chapter).where(Chapter.course_id == cid).order_by(Chapter.chapter_order)
            chapters = (await self.session.exec(stmt)).all()

            total_sections = 0
            completed_sections = 0
            for ch in chapters:
                stmt = select(Section).where(Section.chapter_id == ch.chapter_id)
                sections = (await self.session.exec(stmt)).all()
                total_sections += len(sections)

                if sections:
                    section_ids = [s.section_id for s in sections]
                    stmt = select(SectionCompletionRecord).where(
                        SectionCompletionRecord.student_id == student_id,
                        SectionCompletionRecord.section_id.in_(section_ids),
                    )
                    completed = (await self.session.exec(stmt)).all()
                    completed_sections += len(completed)

            progress = round(completed_sections / total_sections * 100) if total_sections > 0 else 0

            courses.append(
                {
                    "course_id": str(cid),
                    "course_name": course.course_name,
                    "course_cover": course.course_cover,
                    "progress": progress,
                }
            )
        return courses

    async def get_student_study_stats(self, student_id: str) -> dict:
        stmt = select(CourseRegistrationRecord.course_id).where(CourseRegistrationRecord.student_id == student_id)
        course_ids = list((await self.session.exec(stmt)).all())

        total_courses = len(course_ids)
        completed_tasks = 0
        total_tasks = 0

        for cid in course_ids:
            stmt = select(Task.task_id).where(Task.course_id == cid)
            task_ids = list((await self.session.exec(stmt)).all())
            total_tasks += len(task_ids)

            if task_ids:
                stmt = select(TaskCompletion).where(
                    TaskCompletion.student_id == student_id,
                    TaskCompletion.task_id.in_(task_ids),
                )
                completed = (await self.session.exec(stmt)).all()
                completed_tasks += len(completed)

        return {
            "total_courses": total_courses,
            "completed_tasks": completed_tasks,
            "total_tasks": total_tasks,
        }

    async def get_student_course_context(
        self,
        course_id,
        student_id: str,
        current_task_id: int,
        current_task_results: list,
    ) -> dict | None:
        course = await self.session.get(Course, course_id)
        if not course:
            return None
        student = await self.session.get(Student, student_id)
        if not student:
            return None

        sections_data = []
        section_records = (
            await self.session.exec(
                select(SectionCompletionRecord, Section.section_title, Section.description, Chapter.chapter_title)
                .join(Section, SectionCompletionRecord.section_id == Section.section_id)
                .join(Chapter, Section.chapter_id == Chapter.chapter_id)
                .where(
                    SectionCompletionRecord.student_id == student_id,
                    Chapter.course_id == course_id,
                )
            )
        ).all()

        for rec, title, desc, chapter_title in section_records:
            sections_data.append(
                {
                    "chapter_name": chapter_title,
                    "section_title": title,
                    "description": desc,
                    "is_completed": True,
                    "learning_effect": rec.learning_effect,
                }
            )

        tasks_data = []
        all_completions = (
            await self.session.exec(
                select(TaskCompletion).where(
                    TaskCompletion.student_id == student_id,
                    TaskCompletion.task_id.in_(select(Task.task_id).where(Task.course_id == course_id)),
                )
            )
        ).all()

        for comp in all_completions:
            task = await self.session.get(Task, comp.task_id)
            if not task:
                continue

            quiz_items = task.quiz or []
            std_ans_items = task.answer or []
            stu_ans_items = comp.answer or []

            std_answer_map = {
                item.get("question_id"): item.get("correct_answer")
                for item in std_ans_items
                if isinstance(item, dict) and item.get("question_id")
            }
            student_answer_map = {
                item.get("question_id"): item.get("answer")
                for item in stu_ans_items
                if isinstance(item, dict) and item.get("question_id")
            }

            questions_detail = []
            for q in quiz_items:
                if not isinstance(q, dict) or not q.get("question_id"):
                    continue
                q_id = q.get("question_id")

                options_map = {}
                raw_options = q.get("options") or []
                clean_options_for_ai = []

                for opt in raw_options:
                    if isinstance(opt, dict) and opt.get("id") and opt.get("content"):
                        options_map[opt["id"]] = opt["content"]
                        clean_options_for_ai.append({"content": opt["content"]})

                std_ans_text = std_answer_map.get(q_id)
                stu_ans_text = student_answer_map.get(q_id)

                def _replace_id_with_content(answer, opts_map):
                    if not answer:
                        return answer
                    if isinstance(answer, list):
                        return [opts_map.get(item, item) for item in answer]
                    if isinstance(answer, str):
                        return opts_map.get(answer, answer)
                    return answer

                readable_std_ans = _replace_id_with_content(std_ans_text, options_map) if std_ans_text else None
                readable_stu_ans = _replace_id_with_content(stu_ans_text, options_map) if stu_ans_text else None

                q_detail = {
                    "type": q.get("type"),
                    "title": q.get("title"),
                    "options": clean_options_for_ai,
                    "correct_answer": readable_std_ans,
                    "student_answer": readable_stu_ans,
                }
                if task.task_id == current_task_id:
                    res = next((r for r in current_task_results if str(r.get("question_id")) == str(q_id)), None)
                    if res:
                        q_detail["score"] = res.get("score")
                        q_detail["is_ai_graded"] = res.get("is_ai_graded")

                questions_detail.append(q_detail)

            tasks_data.append(
                {
                    "task_title": task.task_title,
                    "final_score": comp.task_scores,
                    "questions_detail": questions_detail,
                }
            )

        if not sections_data and not tasks_data:
            return None

        return {
            "student_name": student.username,
            "course_name": course.course_name,
            "learning_progress": sections_data,
            "tasks_performance": tasks_data,
        }
