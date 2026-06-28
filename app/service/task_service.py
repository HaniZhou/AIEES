import uuid
from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import db
from app.core.exceptions import AppBusinessException
from app.model.models import (
    AnalysisTask,
    AnalysisTaskCompletion,
    Chapter,
    Course,
    CourseRegistrationRecord,
    Section,
    SectionCompletionRecord,
    Task,
    TaskCompletion,
)
from app.util.time_util import format_utc_time
from fastapi import Depends


class TaskService:
    """任务 CRUD + 提交 + 评分触发"""

    def __init__(self, session: AsyncSession = Depends(db.get_session)):
        self.session = session

    async def submit_task_answer(self, course_id: uuid.UUID, task_id: int, student_id: str, answers: list) -> int:
        stmt = select(Task).where(Task.task_id == task_id)
        task = (await self.session.exec(stmt)).one_or_none()
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")
        stmt = select(CourseRegistrationRecord).where(
            CourseRegistrationRecord.student_id == student_id,
            CourseRegistrationRecord.course_id == course_id,
        )
        if not (await self.session.exec(stmt)).first():
            raise AppBusinessException(403, "无权访问此课程")
        stmt = select(TaskCompletion).where(
            TaskCompletion.task_id == task_id,
            TaskCompletion.student_id == student_id,
        )
        if (await self.session.exec(stmt)).first():
            raise AppBusinessException(400, "已提交过答案")
        if task.deadline and datetime.now(UTC) > task.deadline:
            raise AppBusinessException(400, "任务已过截止时间，无法提交")

        completion_record = TaskCompletion(
            task_id=task_id,
            student_id=student_id,
            answer=answers,
            task_scores=0,
            task_analysis="grading",
        )
        self.session.add(completion_record)
        await self.session.flush()
        await self.session.refresh(completion_record)
        if completion_record.completion_id is None:
            raise AppBusinessException(500, "系统异常：提交记录主键生成失败")
        return completion_record.completion_id

    async def submit_gai_task(self, course_id: uuid.UUID, task_id: int, student_id: str, messages: list) -> int:
        stmt = select(AnalysisTask).where(AnalysisTask.analysis_task_id == task_id)
        task = (await self.session.exec(stmt)).one_or_none()
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")
        stmt = select(CourseRegistrationRecord).where(
            CourseRegistrationRecord.student_id == student_id,
            CourseRegistrationRecord.course_id == course_id,
        )
        if not (await self.session.exec(stmt)).first():
            raise AppBusinessException(403, "无权访问此课程")
        stmt = select(AnalysisTaskCompletion).where(
            AnalysisTaskCompletion.analysis_task_id == task_id,
            AnalysisTaskCompletion.student_id == student_id,
        )
        if (await self.session.exec(stmt)).first():
            raise AppBusinessException(400, "已提交过任务")
        if task.deadline and datetime.now(UTC) > task.deadline:
            raise AppBusinessException(400, "任务已过截止时间，无法提交")

        completion_record = AnalysisTaskCompletion(
            analysis_task_id=task_id,
            student_id=student_id,
            messages={"messages": messages},
            analysis_result="AI正在分析中",
            course_id=course_id,
        )
        self.session.add(completion_record)
        await self.session.commit()
        await self.session.refresh(completion_record)
        return completion_record.completion_id

    async def student_complete_section(self, course_id: uuid.UUID, section_id: int, student_id: str) -> None:
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
        existing = (await self.session.exec(stmt)).one_or_none()
        if existing:
            return

        record = SectionCompletionRecord(section_id=section_id, student_id=student_id, learning_effect=0)
        self.session.add(record)
        await self.session.flush()

    async def student_feedback_section(
        self, course_id: uuid.UUID, section_id: int, student_id: str, difficulty: int
    ) -> None:
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
        record = (await self.session.exec(stmt)).one_or_none()
        if record and record.learning_effect and record.learning_effect > 0:
            raise AppBusinessException(400, "反馈已提交")
        if record:
            record.learning_effect = difficulty
            self.session.add(record)
        else:
            new_record = SectionCompletionRecord(
                section_id=section_id,
                student_id=student_id,
                learning_effect=difficulty,
            )
            self.session.add(new_record)
        await self.session.flush()

    async def get_analysis_task_info(self, task_id: int) -> dict | None:
        stmt = select(AnalysisTask).where(AnalysisTask.analysis_task_id == task_id)
        task = (await self.session.exec(stmt)).one_or_none()
        if not task:
            return None
        return {
            "task_description": task.task_description or "",
            "analysis_description": task.analysis_description or "",
            "evaluation_criterion": task.evaluation_criterion or "",
        }

    async def update_grading_result(self, completion_id: int, final_score: float, analysis_text: str) -> None:
        stmt = select(TaskCompletion).where(TaskCompletion.completion_id == completion_id)
        record = (await self.session.exec(stmt)).one_or_none()
        if record:
            record.task_scores = final_score
            record.task_analysis = analysis_text
            self.session.add(record)
            await self.session.flush()

    async def get_tasks_by_course(self, course_id: uuid.UUID, user_id: str, role: str) -> list[dict]:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course:
            raise AppBusinessException(404, "课程不存在")
        if role == "teacher" and course.teacher_id != user_id:
            raise AppBusinessException(403, "无权查看此课程")
        elif role == "student":
            stmt = select(CourseRegistrationRecord).where(
                CourseRegistrationRecord.student_id == user_id,
                CourseRegistrationRecord.course_id == course_id,
            )
            if not (await self.session.exec(stmt)).first():
                raise AppBusinessException(403, "无权访问此课程")

        stmt = select(Task).where(Task.course_id == course_id).order_by(Task.task_id.desc())
        tasks = (await self.session.exec(stmt)).all()

        completed_task_ids: set[int] = set()
        if role == "student" and tasks:
            stmt = select(TaskCompletion.task_id).where(TaskCompletion.student_id == user_id)
            completed_task_ids = set((await self.session.exec(stmt)).all())

        result: list[dict] = []
        for t in tasks:
            item: dict = {
                "task_id": t.task_id,
                "task_title": t.task_title,
                "deadline": format_utc_time(t.deadline),
            }
            if role == "student":
                item["is_completed"] = t.task_id in completed_task_ids
            result.append(item)
        return result

    async def get_task_detail_for_student(self, course_id: uuid.UUID, task_id: int, student_id: str | None) -> dict:
        stmt = select(Task).where(Task.task_id == task_id)
        task = (await self.session.exec(stmt)).one_or_none()
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")
        if student_id:
            stmt = select(CourseRegistrationRecord).where(
                CourseRegistrationRecord.student_id == student_id,
                CourseRegistrationRecord.course_id == course_id,
            )
            if not (await self.session.exec(stmt)).first():
                raise AppBusinessException(403, "无权访问此课程")

        quiz_items = task.quiz or []
        response = {
            "task_title": task.task_title,
            "deadline": format_utc_time(task.deadline),
            "quiz": quiz_items,
            "is_completed": False,
        }
        if student_id:
            stmt = select(TaskCompletion).where(
                TaskCompletion.task_id == task_id,
                TaskCompletion.student_id == student_id,
            )
            completion = (await self.session.exec(stmt)).one_or_none()
            if completion:
                response.update(
                    {
                        "is_completed": True,
                        "student_answers": completion.answer,
                        "task_scores": completion.task_scores,
                        "task_analysis": completion.task_analysis,
                    }
                )
        return response

    async def get_task_detail_for_edit(self, course_id: uuid.UUID, task_id: int, teacher_id: str) -> dict:
        stmt = select(Task).where(Task.task_id == task_id)
        task = (await self.session.exec(stmt)).one_or_none()
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权操作此课程")
        return {
            "task_title": task.task_title,
            "deadline": format_utc_time(task.deadline),
            "quiz": task.quiz if task.quiz else [],
            "answer": task.answer if task.answer else [],
        }

    async def get_task_review_data(self, course_id: uuid.UUID, task_id: int, student_id: str) -> dict:
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
        stmt = select(Task).where(Task.task_id == task_id)
        task = (await self.session.exec(stmt)).one_or_none()
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")
        stmt = select(TaskCompletion).where(
            TaskCompletion.task_id == task_id,
            TaskCompletion.student_id == student_id,
        )
        completion = (await self.session.exec(stmt)).one_or_none()
        if not completion:
            raise AppBusinessException(404, "任务未提交，无法查看回顾")

        quiz_items = task.quiz or []
        answer_items = task.answer or []
        student_answers = completion.answer or []

        correct_answer_map = {
            item.get("question_id"): item.get("correct_answer") for item in answer_items if isinstance(item, dict)
        }
        std_answer_map = {
            item.get("question_id"): item.get("answer") for item in student_answers if isinstance(item, dict)
        }

        questions_review = []
        for q_item in quiz_items:
            if not isinstance(q_item, dict):
                continue
            q_id = q_item.get("question_id")
            questions_review.append(
                {
                    "question_id": q_id,
                    "student_answer": std_answer_map.get(q_id),
                    "correct_answer": correct_answer_map.get(q_id),
                }
            )

        return {
            "task_score": completion.task_scores,
            "ai_analysis": completion.task_analysis if completion.task_analysis else "",
            "questions": questions_review,
        }

    async def get_grading_data(self, task_completion_id: int) -> dict | None:
        stmt = select(TaskCompletion).where(TaskCompletion.completion_id == task_completion_id)
        completion = (await self.session.exec(stmt)).one_or_none()
        if not completion:
            return None
        stmt = select(Task).where(Task.task_id == completion.task_id)
        task = (await self.session.exec(stmt)).one_or_none()
        if not task:
            return None
        return {
            "quiz": task.quiz or [],
            "answer": task.answer or [],
            "student_answer": completion.answer or [],
        }

    async def save_grading_result(self, completion_id: int, final_score: float, analysis_text: str) -> None:
        stmt = select(TaskCompletion).where(TaskCompletion.completion_id == completion_id)
        record = (await self.session.exec(stmt)).one_or_none()
        if record:
            record.task_scores = final_score
            record.task_analysis = analysis_text
            self.session.add(record)
            await self.session.commit()
