from datetime import datetime

from pydantic import BaseModel


class GaiTaskCreateUpdate(BaseModel):
    """GAI 任务创建/更新载荷"""
    analysis_task_title: str
    task_description: str
    analysis_description: str
    evaluation_criterion: str
    deadline: datetime | None = None


class GaiChatRequest(BaseModel):
    messages: list[dict]


class GaiSubmitRequest(BaseModel):
    messages: list[dict]
