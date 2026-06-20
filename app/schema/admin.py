from pydantic import BaseModel, Field


class TeacherUpdate(BaseModel):
    """教师更新请求体（禁止修改所属组织）"""
    id: str
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=1, description="留空则不修改")


class StudentUpdate(BaseModel):
    """学生更新请求体"""
    id: str
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=1, description="留空则不修改")
    class_id: int | None = Field(default=None, description="留空则不修改，修改时会校验禁止跨组织转班")


class DashboardOverview(BaseModel):
    """数据面板总览模型"""
    total_students: int = 0
    total_teachers: int = 0
    total_courses: int = 0
    active_users_today: int = 0
    model_config = {"from_attributes": True}
