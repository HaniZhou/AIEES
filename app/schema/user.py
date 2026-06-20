from pydantic import BaseModel, Field

from app.schema.enums import PhaseType, RoleType


class UserLogin(BaseModel):
    """登录请求体"""
    id: str
    role: RoleType
    password: str
    captcha_key: str | None = None
    captcha_code: str | None = None


class StudentRegister(BaseModel):
    """学生注册"""
    id: str
    username: str = Field(max_length=255)
    password: str
    student_class: str
    organization_name: str


class TeacherRegister(BaseModel):
    """教师注册"""
    id: str
    username: str = Field(max_length=255)
    password: str
    organization_name: str


class UserPublish(BaseModel):
    """返回给前端的用户公开信息"""
    id: str
    role: RoleType
    username: str = Field(max_length=255)
    student_class: str = Field(default="", description="所属班级名称，教师和管理员返回空字符串")
    phase: PhaseType = Field(description="所属机构的适用学段")


class UserInDB(BaseModel):
    """数据库入库模型"""
    id: str
    role: RoleType
    username: str = Field(max_length=255)
    organization_id: int | None = None
    class_id: int | None = None
    hashed_password: str


class Token(BaseModel):
    """返回token"""
    access_token: str | None
    token_type: str | None
    user: UserPublish | None


class TokenData(BaseModel):
    """token数据"""
    id: str
    role: RoleType
    phase: PhaseType


class DeleteUserRequest(BaseModel):
    """删除用户请求体"""
    id: str


class UserUpdatePassword(BaseModel):
    """修改密码请求模型"""
    old_password: str
    new_password: str
