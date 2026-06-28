"""教学分析任务：每日定时触发、单课程分析"""

import json
import uuid

from sqlmodel import select

from app.core.ai_client import llm
from app.core.database import db
from app.core.logging import get_logger
from app.core.prompts import Prompt
from app.model.models import Course
from app.service.course_service import CourseService
from app.task.broker import broker

job_logger = get_logger(__name__)


async def get_all_course_ids() -> list[uuid.UUID]:
    async with db.async_session_factory() as session:
        stmt = select(Course.course_id)
        return list((await session.exec(stmt)).all())


@broker.task(schedule=[{"cron": "0 3 * * *"}])
async def daily_update_all_courses_analysis_job():
    """每日凌晨3点定时任务：查询所有课程，逐个入队分析任务"""
    job_logger.info("[Cron Job] 开始触发每日课程教学分析任务...")
    try:
        course_ids = await get_all_course_ids()
        if not course_ids:
            job_logger.info("当前系统没有课程，跳过分析。")
            return
        for cid in course_ids:
            await process_single_course_analysis_job.kiq(course_id=str(cid))
        job_logger.info(f"已成功将 {len(course_ids)} 个课程的分析任务推入队列。")
    except Exception as e:
        job_logger.error(f"每日课程分析任务触发失败: {str(e)}")


@broker.task()
async def process_single_course_analysis_job(course_id: str):
    """单个课程的教学分析任务"""
    try:
        job_logger.info(f"开始分析课程: {course_id}")
        async with db.async_session_factory() as session:
            svc = CourseService(session=session)
            context_data = await svc.get_course_full_context(uuid.UUID(course_id))
        if not context_data:
            job_logger.warning(f"课程 {course_id} 无有效数据或无学生加入，跳过分析。")
            return
        json_str = json.dumps(context_data, ensure_ascii=False, indent=2)
        sys_prompt = Prompt.TEACHER_COURSE_ANALYSIS_SYSTEM_PROMPT.format(course_full_data=json_str)
        analysis_text = await llm.generate_analysis_text(sys_prompt, "请开始分析。")
        async with db.async_session_factory() as session:
            svc = CourseService(session=session)
            await svc.update_teaching_analysis(uuid.UUID(course_id), analysis_text)
        job_logger.info(f"课程 {course_id} 教学分析更新成功")
    except Exception as e:
        job_logger.error(f"课程 {course_id} 分析过程发生异常: {str(e)}", exc_info=True)
