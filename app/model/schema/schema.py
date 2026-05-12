""" 存放公共的Pydantic模型、Token模型 """
from pydantic import BaseModel, Field, model_validator
from enum import Enum

### ======= Enum 定义 ======= ###
class RoleType(str, Enum):
    """ 用户类型 """
    student = "student"
    teacher = "teacher"
    admin = "admin"

class PhaseType(str, Enum):
    """ 适用学段类型 """
    primary = "小学"
    junior = "初中"
    senior = "高中"
    university = "大学"

### ======= UserModel ======= ###
class UserLogin(BaseModel):
    """
    登陆请求体。
    """
    id: str
    role: RoleType
    password: str
    captcha_key: str | None = None
    captcha_code: str | None = None


class StudentRegister(BaseModel):
    """ 学生注册 """
    id: str
    username: str = Field(max_length=255)
    password: str
    student_class: str
    organization_name: str

class TeacherRegister(BaseModel):
    """ 教师注册 """
    id: str
    username: str = Field(max_length=255)
    password: str
    organization_name: str

class OrganizationCreate(BaseModel):
    """ 创建组织请求体 """
    organization_name: str = Field(max_length=255, description="组织名称")
    phase: PhaseType = Field(description="适用学段（必选）")
    prefix: str = Field(default="", max_length=50, description="登录前缀")

class DeleteUserRequest(BaseModel):
    """ 删除用户请求体 """
    id: str

class DeleteOrgRequest(BaseModel):
    """ 删除组织请求体 """
    organization_id: int

class DeleteClassRequest(BaseModel):
    """ 删除班级请求体 """
    class_id: int

class UserPublish(BaseModel):
    """ 返回给前端的用户公开信息 """
    id: str
    role: RoleType
    username: str = Field(max_length=255)
    student_class: str = Field(default="", description="所属班级名称，教师和管理员返回空字符串")
    phase: PhaseType = Field(description="所属机构的适用学段")

class UserInDB(BaseModel):
    """ 数据库入库模型 """
    id: str
    role: RoleType
    username: str = Field(max_length=255)
    organization_id: int | None = None
    class_id: int | None = None
    hashed_password: str

#### ======= TokenModel ======= ####
class Token(BaseModel):
    """ 返回token """
    access_token: str | None
    token_type: str | None
    user: UserPublish | None

class TokenData(BaseModel):
    """ token数据 """
    id: str | None = None
    role: RoleType | None = None
    phase: PhaseType | None = None

#### ======= 数据面板模型 ======= ####
class DashboardOverview(BaseModel):
    """ 示例：数据面板总览模型 """
    total_students: int = 0
    total_teachers: int = 0
    total_courses: int = 0
    active_users_today: int = 0
    model_config = {"from_attributes": True}

class ChatMessage(BaseModel):
    role: str = Field(description="角色: user / assistant")
    content: str = Field(description="消息内容")

class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(description="对话历史")

    @model_validator(mode='after')
    def block_system_role_injection(self) -> 'ChatRequest':
        """函数目的：安全拦截，防止前端恶意注入系统提示词。
        """
        if any(msg.role.lower() == "system" for msg in self.messages):
            raise ValueError("安全拦截：禁止在对话历史中传递系统提示词")
        return self



class ScenarioType(Enum):
    normal = "normal"
    agi = "agi"


class OrganizationUpdate(BaseModel):
    """ 组织更新请求体 """
    organization_id: int
    organization_name: str | None = Field(default=None, max_length=255)
    phase: PhaseType | None = None
    prefix: str | None = Field(default=None, max_length=50)

class ClassCreate(BaseModel):
    """ 班级创建请求体 """
    class_name: str = Field(max_length=255, description="班级名称")
    organization_id: int = Field(description="所属组织ID")

class ClassUpdate(BaseModel):
    """ 班级更新请求体（禁止修改所属组织） """
    class_id: int
    class_name: str | None = Field(default=None, max_length=255)

class TeacherUpdate(BaseModel):
    """ 教师更新请求体（禁止修改所属组织） """
    id: str
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=1, description="留空则不修改")

class StudentUpdate(BaseModel):
    """ 学生更新请求体 """
    id: str
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=1, description="留空则不修改")
    class_id: int | None = Field(default=None, description="留空则不修改，修改时会校验禁止跨组织转班")

class UserUpdatePassword(BaseModel):
    """函数目的：修改密码请求模型"""
    old_password: str
    new_password: str

    @model_validator(mode='after')
    def check_passwords_match(self):
        """函数目的：字段级校验，确保新密码与确认密码一致"""
        if self.new_password != self.confirm_password:
            raise ValueError("两次输入的密码不一致")
        return self