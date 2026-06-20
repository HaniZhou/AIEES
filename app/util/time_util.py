from datetime import UTC, datetime
from typing import Any


def format_utc_time(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_chat_history(raw_messages: Any) -> list[dict]:
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
