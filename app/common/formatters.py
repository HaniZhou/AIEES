""" 数据格式化与校验工具函数 """
from app.core.exceptions import AppBusinessException


def _validate_task_payload_consistency(quiz: list[dict], answer: list[dict]) -> None:

    quiz_ids = {q.get("question_id") for q in quiz if q.get("question_id")}
    answer_ids = {a.get("question_id") for a in answer if a.get("question_id")}

    if quiz_ids != answer_ids:
        raise AppBusinessException(400, "题目与答案的 question_id 不完全匹配，严禁依赖数组下标对齐")

    for item in answer:
        q_type = item.get("type")
        c_answer = item.get("correct_answer")
        if q_type in ("single", "multiple"):
            if not isinstance(c_answer, list) or len(c_answer) == 0:
                raise AppBusinessException(400, "单选/多选题的正确答案必须是字符串数组")
            if q_type == "single" and len(c_answer) != 1:
                raise AppBusinessException(400, "单选题的正确答案数组长度必须为 1")
        elif q_type == "judge":
            if not isinstance(c_answer, list) or len(c_answer) != 1 or c_answer[0] not in ("true", "false"):
                raise AppBusinessException(400, "判断题答案必须为 ['true'] 或 ['false']")
        elif q_type == "subjective":
            if not isinstance(c_answer, str):
                raise AppBusinessException(400, "主观题答案必须为字符串类型")
