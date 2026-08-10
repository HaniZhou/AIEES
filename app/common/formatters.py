"""数据格式化与校验工具函数"""

from app.core.exceptions import AppBusinessException


def replace_id_with_content(answer: str | list[str] | None, options_map: dict[str, str]) -> str | list[str] | None:
    """将选项 ID 替换为真实文本内容"""
    if not answer:
        return answer
    if isinstance(answer, list):
        return [options_map.get(item, item) for item in answer]
    return options_map.get(answer, answer)


def _validate_task_payload_consistency(quiz: list[dict], answer: list[dict]) -> None:
    """校验题目与答案的ID映射关系及各题型答案字段格式，不匹配则抛异常。"""
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
