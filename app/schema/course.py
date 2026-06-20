from uuid import UUID

from pydantic import BaseModel, Field


class CourseInfo(BaseModel):
    """创建课程"""
    course_name: str
    teacher_id: str
    course_cover: str
    teaching_plan: str
    invited_code: str
    is_invitation_valid: bool


class CourseRead(BaseModel):
    """课程只读模型"""
    course_id: UUID
    course_name: str
    course_cover: str
    model_config = {"from_attributes": True}


class CourseDetailRead(BaseModel):
    """课程详情只读模型"""
    course_name: str
    course_cover: str
    invited_code: str
    is_invitation_valid: bool
    model_config = {"from_attributes": True}


class CourseUpdate(BaseModel):
    """课程局部更新模型 (PATCH)"""
    course_name: str | None = None
    course_cover: str | None = None
    teaching_plan: str | None = None
    is_invitation_valid: bool | None = None


class JoinCourseRequest(BaseModel):
    """学生加入课程请求体"""
    invite_code: str = Field(min_length=6, max_length=6)
