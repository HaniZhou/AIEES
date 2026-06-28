"""评分任务：批改学生作业、触发学情分析"""

import json
import re

from app.core.ai_client import llm
from app.core.database import db
from app.core.logging import get_logger
from app.core.prompts import Prompt
from app.service.analysis_service import AnalysisService
from app.service.student_service import StudentService
from app.service.task_service import TaskService
from app.task.broker import broker

job_logger = get_logger(__name__)


async def _trigger_course_analysis(course_id: str, student_id: str, current_task_id: int, current_task_results: list):
    try:
        async with db.async_session_factory() as session:
            student_svc = StudentService(session=session)
            context_data = await student_svc.get_student_course_context(
                course_id,
                student_id,
                current_task_id,
                current_task_results,
            )
        if not context_data:
            llm.logger.warning(f"Analysis context empty for student {student_id} in course {course_id}")
            return
        json_str = json.dumps(context_data, ensure_ascii=False, indent=2)
        sys_prompt = Prompt.STUDENT_LEARNING_ANALYSIS_SYSTEM_PROMPT.format(json_data=json_str)
        analysis_text = await llm.generate_analysis_text(sys_prompt, "请开始分析。")
        async with db.async_session_factory() as session:
            analysis_svc = AnalysisService(session=session)
            await analysis_svc.upsert_student_analysis_description(
                course_id=course_id,
                student_id=student_id,
                analysis_content=analysis_text,
            )
            await session.commit()
    except Exception as e:
        llm.logger.error(
            f"Failed to generate/update learning analysis for student {student_id}, course {course_id}: {str(e)}"
        )


def _replace_id_with_content(answer, options_map: dict) -> str | list[str] | None:
    if not answer:
        return answer
    if isinstance(answer, list):
        return [options_map.get(item, item) for item in answer]
    if isinstance(answer, str):
        return options_map.get(answer, answer)
    return answer


@broker.task()
async def process_task_grading_job(task_completion_id: int, course_id: str, student_id: str, task_id: int):
    try:
        async with db.async_session_factory() as session:
            task_svc = TaskService(session=session)
            task_data = await task_svc.get_grading_data(task_completion_id)
        if not task_data:
            llm.logger.error(f"Grading failed: Completion record {task_completion_id} not found.")
            return
        quiz = task_data.get("quiz") or []
        std_answers = task_data.get("answer") or []
        student_answers = task_data.get("student_answer") or []
        total_questions = len(quiz)
        if total_questions == 0:
            async with db.async_session_factory() as session:
                task_svc2 = TaskService(session=session)
                await task_svc2.save_grading_result(task_completion_id, 0, "任务没有题目，无法评分")
            return
        std_answer_map = {
            item.get("question_id"): item.get("correct_answer")
            for item in std_answers
            if isinstance(item, dict) and item.get("question_id")
        }
        student_answer_map = {
            item.get("question_id"): item.get("answer")
            for item in student_answers
            if isinstance(item, dict) and item.get("question_id")
        }
        score_per_question = 100.0 / total_questions
        total_score = 0.0
        question_results = []
        for q_item in quiz:
            if not isinstance(q_item, dict):
                continue
            q_id = q_item.get("question_id")
            if not q_id:
                llm.logger.warning(f"Quiz item missing question_id in task {task_id}. Skipping.")
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
                sys_prompt = '你是一个严格的阅卷专家。请分析学生的作答与标准答案的契合度。你必须且只能返回一个JSON格式：{"score_ratio": 0.85}。score_ratio代表该题得分在满分中的占比(0到1之间的小数)。不要返回任何其他文字。'
                user_content = f"题目：{title}\n标准答案：{std_ans}\n学生作答：{stu_ans}"
                try:
                    ai_response = await llm.generate_analysis_text(sys_prompt, user_content)
                    clean_res = ai_response.replace("```json", "").replace("```", "").strip()
                    res_json = json.loads(clean_res)
                    ratio = float(res_json.get("score_ratio", 0))
                    ratio = min(max(ratio, 0.0), 1.0)
                except Exception as parse_err:
                    llm.logger.warning(
                        f"AI score JSON parse failed for task {task_id}, q {q_id}: {parse_err}. Trying regex fallback."
                    )
                    match = re.search(r"(\d+(?:\.\d+)?)", ai_response)
                    if match:
                        ratio = float(match.group(1))
                        ratio = min(max(ratio, 0.0), 1.0)
                    else:
                        ratio = 0.0
                        llm.logger.error(f"AI score regex fallback failed for task {task_id}, q {q_id}. Score set to 0.")
                actual_score = score_per_question * ratio
            total_score += actual_score
            question_results.append(
                {"question_id": q_id, "type": q_type, "score": round(actual_score, 2), "is_ai_graded": is_ai_graded}
            )
        final_score = round(total_score, 2)
        try:
            context_details = []
            for q_item in quiz:
                if not isinstance(q_item, dict) or not q_item.get("question_id"):
                    continue
                q_id = q_item.get("question_id")
                res = next((r for r in question_results if r.get("question_id") == q_id), None)
                is_correct = res and res.get("score", 0) >= score_per_question - 0.01
                context_details.append(
                    {
                        "题型": q_item.get("type"),
                        "题目": q_item.get("title"),
                        "学生作答": student_answer_map.get(q_id),
                        "标准答案": std_answer_map.get(q_id),
                        "是否正确": "正确" if is_correct else "错误",
                        "得分": res.get("score", 0) if res else 0,
                    }
                )
            analysis_sys_prompt = "你是一个资深的教育评估专家。请根据学生的测验作答详情和得分情况，精准定位学生的知识薄弱点，并给出针对性的学习建议。\n【严格要求】：1. 严禁输出任何问候语、解释性前缀（如`好的，以下是分析`）或总结性后缀；3. 语言需精炼专业，分点列出。"
            analysis_user_prompt = (
                f"学生总分：{final_score}/100。作答详情：{json.dumps(context_details, ensure_ascii=False)}"
            )
            ai_analysis_response = await llm.generate_analysis_text(analysis_sys_prompt, analysis_user_prompt)
        except Exception as analysis_err:
            llm.logger.error(
                f"Failed to generate task weakness analysis for completion {task_completion_id}: {str(analysis_err)}"
            )
            ai_analysis_response = "评分完成，但AI学情分析生成异常"
        async with db.async_session_factory() as session:
            task_svc3 = TaskService(session=session)
            await task_svc3.save_grading_result(task_completion_id, final_score, ai_analysis_response)
        await _trigger_course_analysis(course_id, student_id, task_id, question_results)
    except Exception as e:
        llm.logger.error(f"Unexpected error in grading job for completion {task_completion_id}: {str(e)}")
        try:
            async with db.async_session_factory() as session:
                task_svc4 = TaskService(session=session)
                await task_svc4.save_grading_result(task_completion_id, 0, f"评分过程发生系统异常: {str(e)}")
        except BaseException:
            pass
