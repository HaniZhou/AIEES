""" ARQ 异步任务队列定义 """
import logging
import re
import json
from arq import create_pool
from app.core.AI_tools import generate_gai_analysis_text, logger as ai_logger
from arq.connections import RedisSettings
from arq.cron import cron
from app.crud.db import (
    async_session_factory,
    db_get_task_raw_for_grading,
    db_update_task_grading_result,
    db_get_student_course_context_for_analysis,
    db_upsert_student_analysis_description,
    db_get_all_active_course_ids,
    db_get_course_full_context_for_teacher_analysis,
    db_update_course_teaching_analysis
)
from app.Config import Prompt, SecretConfig, UrlConfig
import uuid
# 任务队列日志
job_logger = logging.getLogger("arq_jobs")
job_logger.setLevel(logging.INFO)
# 任务队列日志
job_logger = logging.getLogger("arq_jobs")
job_logger.setLevel(logging.INFO)

async def startup(ctx):
    """ ARQ Worker 启动时的初始化 """
    ctx['redis'] = await create_pool(RedisSettings(host=UrlConfig.REDIS_HOST, port=UrlConfig.REDIS_PORT, password=SecretConfig.REDIS_PASSWORD))

async def shutdown(ctx):
    """ ARQ Worker 关闭时的清理 """
    await ctx['redis'].close()
async def process_task_grading_job(ctx, task_completion_id: int, course_id: str, student_id: str, task_id: int):
    """后台异步执行测验评分、生成单任务学情分析及触发课程级学情分析。"""
    try:
        task_data = await db_get_task_raw_for_grading(task_completion_id)
        if not task_data:
            ai_logger.error(f"Grading failed: Completion record {task_completion_id} not found.")
            return
        quiz = task_data.get("quiz") or []
        std_answers = task_data.get("answer") or []
        student_answers = task_data.get("student_answer") or []

        total_questions = len(quiz)
        if total_questions == 0:
            await db_update_task_grading_result(task_completion_id, 0, "任务没有题目，无法评分")
            return
        std_answer_map = {
            item.get("question_id"): item.get("correct_answer")
            for item in std_answers if isinstance(item, dict) and item.get("question_id")
        }
        student_answer_map = {
            item.get("question_id"): item.get("answer")
            for item in student_answers if isinstance(item, dict) and item.get("question_id")
        }
        score_per_question = 100.0 / total_questions
        total_score = 0.0
        question_results = []
        for q_item in quiz:
            if not isinstance(q_item, dict):
                continue
            q_id = q_item.get("question_id")
            if not q_id:
                ai_logger.warning(f"Quiz item missing question_id in task {task_id}. Skipping.")
                continue
            q_type = q_item.get("type")
            title = q_item.get("title", "")
            std_ans = std_answer_map.get(q_id)
            stu_ans = student_answer_map.get(q_id)

            actual_score = 0.0
            is_ai_graded = False
            if q_type in ["single", "multiple", "judge"]:
                std_set = set(std_ans) if isinstance(std_ans, list) else ({std_ans} if std_ans else set())
                stu_set = set(stu_ans) if isinstance(stu_ans, list) else ({stu_ans} if stu_ans else set())
                if std_set and stu_set == std_set:
                    actual_score = score_per_question

            elif q_type == "subjective":
                is_ai_graded = True
                sys_prompt = "你是一个严格的阅卷专家。请分析学生的作答与标准答案的契合度。你必须且只能返回一个JSON格式：{\"score_ratio\": 0.85}。score_ratio代表该题得分在满分中的占比(0到1之间的小数)。不要返回任何其他文字。"
                user_content = f"题目：{title}\n标准答案：{std_ans}\n学生作答：{stu_ans}"
                try:
                    ai_response = await generate_gai_analysis_text(sys_prompt, user_content)
                    clean_res = ai_response.replace("```json", "").replace("```", "").strip()
                    res_json = json.loads(clean_res)
                    ratio = float(res_json.get("score_ratio", 0))
                    ratio = min(max(ratio, 0.0), 1.0)
                except Exception as parse_err:
                    ai_logger.warning(f"AI score JSON parse failed for task {task_id}, q {q_id}: {parse_err}. Trying regex fallback.")
                    match = re.search(r"(\d+(?:\.\d+)?)", ai_response)
                    if match:
                        ratio = float(match.group(1))
                        ratio = min(max(ratio, 0.0), 1.0)
                    else:
                        ratio = 0.0
                        ai_logger.error(f"AI score regex fallback failed for task {task_id}, q {q_id}. Score set to 0.")
                actual_score = score_per_question * ratio
            total_score += actual_score
            question_results.append({
                "question_id": q_id,
                "type": q_type,
                "score": round(actual_score, 2),
                "is_ai_graded": is_ai_graded
            })
        final_score = round(total_score, 2)
        try:
            context_details = []
            for q_item in quiz:
                if not isinstance(q_item, dict) or not q_item.get("question_id"):
                    continue
                q_id = q_item.get("question_id")
                res = next((r for r in question_results if r.get("question_id") == q_id), None)
                is_correct = res and res.get("score", 0) >= score_per_question - 0.01
                context_details.append({
                    "题型": q_item.get("type"),
                    "题目": q_item.get("title"),
                    "学生作答": student_answer_map.get(q_id),
                    "标准答案": std_answer_map.get(q_id),
                    "是否正确": "正确" if is_correct else "错误",
                    "得分": res.get("score", 0) if res else 0
                })
            analysis_sys_prompt = "你是一个资深的教育评估专家。请根据学生的测验作答详情和得分情况，精准定位学生的知识薄弱点，并给出针对性的学习建议。\n【严格要求】：1. 严禁输出任何问候语、解释性前缀（如“好的，以下是分析”）或总结性后缀；3. 语言需精炼专业，分点列出。"
            analysis_user_prompt = f"学生总分：{final_score}/100。作答详情：{json.dumps(context_details, ensure_ascii=False)}"

            ai_analysis_response = await generate_gai_analysis_text(analysis_sys_prompt, analysis_user_prompt)
        except Exception as analysis_err:
            ai_logger.error(f"Failed to generate task weakness analysis for completion {task_completion_id}: {str(analysis_err)}")
            ai_analysis_response = "评分完成，但AI学情分析生成异常"
        await db_update_task_grading_result(task_completion_id, final_score, ai_analysis_response)
        await _trigger_course_analysis(course_id, student_id, task_id, question_results)
    except Exception as e:
        ai_logger.error(f"Unexpected error in grading job for completion {task_completion_id}: {str(e)}")
        try:
            await db_update_task_grading_result(task_completion_id, 0, f"评分过程发生系统异常: {str(e)}")
        except:
            pass
async def _trigger_course_analysis(course_id: str, student_id: str, current_task_id: int, current_task_results: list):
    """提取学生整门课的上下文，调用大模型生成学情分析。"""
    try:
        context_data = await db_get_student_course_context_for_analysis(course_id, student_id, current_task_id, current_task_results)
        if not context_data:
            ai_logger.warning(f"Analysis context empty for student {student_id} in course {course_id}")
            return

        # 将 JSON 数据安全注入到系统提示词
        json_str = json.dumps(context_data, ensure_ascii=False, indent=2)
        sys_prompt = Prompt.STUDENT_LEARNING_ANALYSIS_SYSTEM_PROMPT.format(json_data=json_str)

        # 传入 user_content 触发执行
        analysis_text = await generate_gai_analysis_text(sys_prompt, "请开始分析。")

        await db_upsert_student_analysis_description(
            course_id=course_id,
            student_id=student_id,
            analysis_content=analysis_text
        )
    except Exception as e:
        ai_logger.error(f"Failed to generate/update learning analysis for student {student_id}, course {course_id}: {str(e)}")
# 每日定时课程分析任务
async def daily_update_all_courses_analysis_job(ctx):
    """定时任务入口，遍历所有课程，将单个课程的分析任务推入队列。"""
    job_logger.info("[Cron Job] 开始触发每日课程教学分析任务...")
    try:
        course_ids = await db_get_all_active_course_ids()
        if not course_ids:
            job_logger.info("当前系统没有课程，跳过分析。")
            return

        redis = ctx.get('redis') or await create_pool(
            RedisSettings(host=UrlConfig.REDIS_HOST, port=UrlConfig.REDIS_PORT, password=SecretConfig.REDIS_PASSWORD)
        )

        for course_id in course_ids:
            await redis.enqueue_job('process_single_course_analysis_job', course_id=str(course_id))

        job_logger.info(f"已成功将 {len(course_ids)} 个课程的分析任务推入队列。")

        if not ctx.get('redis'):
            await redis.close()
    except Exception as e:
        job_logger.error(f"每日课程分析任务触发失败: {str(e)}")
async def process_single_course_analysis_job(ctx, course_id: str):
    """执行单个课程的数据提取、AI分析及结果回写。"""
    try:
        job_logger.info(f"开始分析课程: {course_id}")
        context_data = await db_get_course_full_context_for_teacher_analysis(uuid.UUID(course_id))

        if not context_data:
            job_logger.warning(f"课程 {course_id} 无有效数据或无学生加入，跳过分析。")
            return

        # 将全量课程 JSON 数据安全注入到系统提示词的隔离区中
        json_str = json.dumps(context_data, ensure_ascii=False, indent=2)
        sys_prompt = Prompt.TEACHER_COURSE_ANALYSIS_SYSTEM_PROMPT.format(course_full_data=json_str)

        analysis_text = await generate_gai_analysis_text(sys_prompt, "请开始分析。")

        await db_update_course_teaching_analysis(uuid.UUID(course_id), analysis_text)
        job_logger.info(f"课程 {course_id} 教学分析更新成功")
    except Exception as e:
        job_logger.error(f"课程 {course_id} 分析过程发生异常: {str(e)}", exc_info=True)
# ==================== ARQ Worker 统一配置类 ====================
class WorkerSettings:
    """ ARQ Worker 配置"""
    functions = [process_task_grading_job, process_single_course_analysis_job]
    cron_jobs = [
        cron(daily_update_all_courses_analysis_job, hour=3, minute=0, run_at_startup=False)
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(host=UrlConfig.REDIS_HOST, port=UrlConfig.REDIS_PORT, password=SecretConfig.REDIS_PASSWORD)

    # AI 处理时间可能较长
    job_timeout = 900