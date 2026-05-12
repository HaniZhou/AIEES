""" 纯数据格式化与校验工具函数 """
from datetime import datetime, UTC
from typing import Any


def _format_utc_time(dt: datetime | None) -> str:
    """函数目的：强制将 datetime 对象转换为符合规范的 ISO 8601 UTC 字符串。
    参数信息：- dt: datetime | None，待转换的时间对象，输入为空时返回空字符串。
    返回值：str，格式为 'YYYY-MM-DDTHH:MM:SSZ' 的字符串，严禁返回 None。
    """
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_chat_history(raw_messages: Any) -> list[dict]:
    """函数目的：将多种可能形态的前端对话历史统一标准化为包含 id、role、content 的字典列表。
    参数信息：- raw_messages: Any，可能是 list、dict 或单条消息字典。
    返回值：list[dict]，标准化后的对话列表。
    """
    messages = []
    if not raw_messages:
        return []
    if isinstance(raw_messages, list):
        messages = raw_messages
    elif isinstance(raw_messages, dict):
        messages = raw_messages.get("messages") or raw_messages.get("chat_history") or (
            [raw_messages] if "role" in raw_messages else [])
    return [
        {"id": msg.get("id", f"msg_{idx + 1}"), "role": msg.get("role", "user"), "content": msg.get("content", "")}
        for idx, msg in enumerate(messages) if isinstance(msg, dict)
    ]


def _validate_task_payload_consistency(quiz: list[dict], answer: list[dict]) -> None:
    """函数目的：强校验题目与答案的 ID 强关联一致性及多态答案格式，违反直接阻断。
    参数信息：- quiz: list[dict]，前端传入的题目列表; - answer: list[dict]，前端传入的答案列表。
    返回值：无，校验失败抛出 AppBusinessException。
    """
    from app.crud.db import AppBusinessException  # 延迟导入避免循环依赖

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