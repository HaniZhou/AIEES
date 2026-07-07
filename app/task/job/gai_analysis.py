"""GAI 分析任务：学生提交对话后异步执行 AI 评估"""

from sqlmodel import select

from app.core.ai_client import llm
from app.core.database import db
from app.core.logging import get_logger
from app.core.prompts import Prompt
from app.model.models import AnalysisTask, AnalysisTaskCompletion
from app.task.broker import broker

job_logger = get_logger(__name__)


@broker.task()
async def process_gai_analysis_job(task_id: int, completion_id: int, messages: list) -> None:
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
        job_logger.error(
            f"GAI analysis execution failed, task_id={task_id}, completion_id={completion_id}, error: {str(e)}"
        )
        async with db.async_session_factory() as session:
            stmt = select(AnalysisTaskCompletion).where(AnalysisTaskCompletion.completion_id == completion_id)
            record = (await session.exec(stmt)).one_or_none()
            if record:
                record.analysis_result = "AI分析失败，请稍后重试"
                session.add(record)
                await session.commit()
