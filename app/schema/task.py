from datetime import datetime

from pydantic import BaseModel, Field

from app.schema.enums import ExamType


class OptionItem(BaseModel):
    """选项对象结构"""
    id: str
    content: str


class QuizItem(BaseModel):
    """题目项"""
    question_id: str
    type: ExamType
    title: str
    options: list[OptionItem] = Field(default_factory=list)


class AnswerItem(BaseModel):
    """答案项（支持多态 correct_answer）"""
    question_id: str
    type: ExamType
    correct_answer: list[str] | str


class TaskCreateAndUpdate(BaseModel):
    """测验任务创建/更新载荷"""
    task_title: str
    deadline: datetime
    quiz: list[QuizItem]
    answer: list[AnswerItem]


class TaskAnswerItem(BaseModel):
    question_id: str
    answer: str | list[str]


class TaskSubmitRequest(BaseModel):
    answers: list[TaskAnswerItem] | list[dict]


class DurationReportRequest(BaseModel):
    """上报学习时长请求体"""
    duration: int = Field(..., gt=0, description="本次学习的秒数（正整数）")
