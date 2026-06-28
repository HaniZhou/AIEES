from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.ai_client import llm
from app.core.database import db
from app.core.exceptions import AppBusinessException
from app.core.logging import get_logger
from app.core.prompts import Prompt
from app.model.models import AnalysisDescription, AnalysisTask, AnalysisTaskCompletion, Course, CourseRegistrationRecord
from app.util.time_util import format_utc_time, normalize_chat_history
from fastapi import Depends

analysis_logger = get_logger(f"{__name__}.analysis")


class AnalysisService:
    """GAI 分析任务 + AI 评估"""

    def __init__(self, session: AsyncSession = Depends(db.get_session)):
        self.session = session

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

    async def update_gai_task_analysis_result(self, completion_id: int, result_text: str) -> None:
        stmt = select(AnalysisTaskCompletion).where(AnalysisTaskCompletion.completion_id == completion_id)
        record = (await self.session.exec(stmt)).one_or_none()
        if record:
            record.analysis_result = result_text
            self.session.add(record)
            await self.session.flush()

    async def upsert_student_analysis_description(self, course_id: str, student_id: str, analysis_content: str) -> None:
        import uuid as _uuid

        course_uuid = _uuid.UUID(course_id)
        stmt = (
            select(AnalysisDescription)
            .where(
                AnalysisDescription.student_id == student_id,
                AnalysisDescription.course_id == course_uuid,
            )
            .order_by(AnalysisDescription.analysis_id.desc())
        )
        existing = (await self.session.exec(stmt)).first()
        if existing:
            existing.analysis_content = analysis_content
            self.session.add(existing)
        else:
            new_record = AnalysisDescription(
                student_id=student_id,
                course_id=course_uuid,
                analysis_content=analysis_content,
            )
            self.session.add(new_record)
        await self.session.flush()

    async def get_gai_tasks_by_course(self, course_id, user_id: str, role: str) -> list[dict]:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course:
            raise AppBusinessException(404, "课程不存在")
        if role == "teacher" and course.teacher_id != user_id:
            raise AppBusinessException(403, "无权查看此课程")

        stmt = (
            select(AnalysisTask)
            .where(AnalysisTask.course_id == course_id)
            .order_by(AnalysisTask.analysis_task_id.desc())
        )
        tasks = (await self.session.exec(stmt)).all()
        result = []
        for t in tasks:
            task_data = {
                "analysis_task_id": t.analysis_task_id,
                "analysis_task_title": t.analysis_task_title,
                "task_description": t.task_description,
                "analysis_description": t.analysis_description,
                "evaluation_criterion": t.evaluation_criterion,
                "deadline": format_utc_time(t.deadline),
                "is_completed": False,
            }
            if role == "student":
                stmt = select(AnalysisTaskCompletion).where(
                    AnalysisTaskCompletion.analysis_task_id == t.analysis_task_id,
                    AnalysisTaskCompletion.student_id == user_id,
                )
                task_data["is_completed"] = (await self.session.exec(stmt)).first() is not None
            result.append(task_data)
        return result

    async def get_gai_task_student_analysis(self, course_id, task_id: int, teacher_id: str, student_id: str) -> dict:
        stmt = select(Course).where(Course.course_id == course_id)
        course = (await self.session.exec(stmt)).one_or_none()
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权查看此课程")
        stmt = select(AnalysisTask).where(AnalysisTask.analysis_task_id == task_id)
        task = (await self.session.exec(stmt)).one_or_none()
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")
        stmt = select(CourseRegistrationRecord).where(
            CourseRegistrationRecord.student_id == student_id,
            CourseRegistrationRecord.course_id == course_id,
        )
        if not (await self.session.exec(stmt)).first():
            raise AppBusinessException(404, "学生不在该课程中")

        stmt = (
            select(AnalysisTaskCompletion)
            .where(
                AnalysisTaskCompletion.course_id == course_id,
                AnalysisTaskCompletion.analysis_task_id == task_id,
                AnalysisTaskCompletion.student_id == student_id,
            )
            .order_by(AnalysisTaskCompletion.completion_id.desc())
        )
        record = (await self.session.exec(stmt)).first()
        if not record:
            return {"chat_history": [], "analysis_text": ""}
        return {"chat_history": normalize_chat_history(record.messages), "analysis_text": record.analysis_result or ""}

    async def execute_gai_analysis(self, task_id: int, completion_id: int, messages: list) -> None:
        """后台执行 GAI 分析，使用独立 session 隔离事务（因含长时间 AI API 调用）"""
        try:
            async with db.async_session_factory() as session:
                stmt = select(AnalysisTask).where(AnalysisTask.analysis_task_id == task_id)
                task = (await session.exec(stmt)).one_or_none()
                task_info = (
                    {
                        "task_description": task.task_description or "",
                        "analysis_description": task.analysis_description or "",
                        "evaluation_criterion": task.evaluation_criterion or "",
                    }
                    if task
                    else None
                )

            if not task_info:
                async with db.async_session_factory() as session:
                    stmt = select(AnalysisTaskCompletion).where(AnalysisTaskCompletion.completion_id == completion_id)
                    record = (await session.exec(stmt)).one_or_none()
                    if record:
                        record.analysis_result = "AI分析失败：任务配置丢失"
                        session.add(record)
                        await session.commit()
                return

            class_info = (
                f"【任务描述】：{task_info.get('task_description', '未提供')}\n"
                f"【分析要求】：{task_info.get('analysis_description', '未提供')}\n"
                f"【评价标准】：{task_info.get('evaluation_criterion', '未提供')}"
            )
            system_prompt = Prompt.TEACHER_ANALYSIS_SYSTEM_PROMPT.format(class_info=class_info)

            chat_history = "\n".join([f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" for msg in messages])
            user_content = f"<INPUT_DATA>\n{chat_history}\n</INPUT_DATA>"

            analysis_text = await llm.generate_analysis_text(system_prompt, user_content)
            async with db.async_session_factory() as session:
                stmt = select(AnalysisTaskCompletion).where(AnalysisTaskCompletion.completion_id == completion_id)
                record = (await session.exec(stmt)).one_or_none()
                if record:
                    record.analysis_result = analysis_text
                    session.add(record)
                    await session.commit()
        except Exception as e:
            analysis_logger.error(
                f"GAI analysis execution failed, task_id={task_id}, completion_id={completion_id}, error: {str(e)}"
            )
            async with db.async_session_factory() as session:
                stmt = select(AnalysisTaskCompletion).where(AnalysisTaskCompletion.completion_id == completion_id)
                record = (await session.exec(stmt)).one_or_none()
                if record:
                    record.analysis_result = "AI分析失败，请稍后重试"
                    session.add(record)
                    await session.commit()
