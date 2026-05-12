""" 课程相关 Pydantic 模型定义必须放置在这里 """
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
from uuid import UUID

class ResourceType(str, Enum):
    """资源类型"""
    pdf = "pdf"
    video = "video"

class CourseInfo(BaseModel):
    """ 创建课程"""
    course_name: str
    teacher_id: str
    course_cover: str
    teaching_plan: str
    invited_code: str
    is_invitation_valid: bool

class CourseRead(BaseModel):
    """ 课程只读模型 """
    course_id: UUID
    course_name: str
    course_cover: str
    model_config = {"from_attributes": True}

class CourseDetailRead(BaseModel):
    """ 课程详情只读模型 """
    course_name: str
    course_cover: str
    invited_code: str
    is_invitation_valid: bool
    model_config = {"from_attributes": True}

class SectionPayload(BaseModel):
    """ 小节更新载荷 """
    section_id: int | None = None
    section_title: str
    section_type: ResourceType
    section_order: int | None = None
    resource_path: str | None = None
    description: str

class ChapterPayload(BaseModel):
    """ 章节更新载荷 """
    chapter_id: int | None = None
    chapter_title: str
    chapter_order: int | None = None
    sub_tasks: list[SectionPayload] = Field(default_factory=list)

class ChapterBatchPayload(BaseModel):
    """ 批量更新总载荷 """
    chapters: list[ChapterPayload]

class ExamType(str, Enum):
    """ 测试题型 """
    single = "single"
    multiple = "multiple"
    judge = "judge"
    subjective = "subjective"

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
    deadline: datetime  # 文档规定必填，若为空 FastAPI 自动拦截 422
    quiz: list[QuizItem]
    answer: list[AnswerItem]

class GaiTaskCreateUpdate(BaseModel):
    """ GAI 任务创建/更新载荷 """
    analysis_task_title: str
    task_description: str
    analysis_description: str
    evaluation_criterion: str
    deadline: datetime | None = None

class CourseUpdate(BaseModel):
    """ 课程局部更新模型 (PATCH) """
    course_name: str | None = None
    course_cover: str | None = None
    teaching_plan: str | None = None
    is_invitation_valid: bool | None = None

class JoinCourseRequest(BaseModel):
    """ 学生加入课程请求体 """
    invite_code: str = Field(min_length=6, max_length=6)

class SectionFeedbackRequest(BaseModel):
    difficulty: int = Field(ge=1, le=5)

class TaskAnswerItem(BaseModel):
    question_id: str
    answer: str | list[str]

class TaskSubmitRequest(BaseModel):
    answers: list[TaskAnswerItem] | list[dict]

class GaiChatRequest(BaseModel):
    messages: list[dict]

class GaiSubmitRequest(BaseModel):
    messages: list[dict]

class DurationReportRequest(BaseModel):
    """ 上报学习时长请求体 """
    duration: int = Field(..., gt=0, description="本次学习的秒数（正整数）")