from pydantic import BaseModel, Field

from app.schema.enums import PhaseType


class OrganizationCreate(BaseModel):
    """创建组织请求体"""
    organization_name: str = Field(max_length=255, description="组织名称")
    phase: PhaseType = Field(description="适用学段（必选）")
    prefix: str = Field(default="", max_length=50, description="登录前缀")


class OrganizationUpdate(BaseModel):
    """组织更新请求体"""
    organization_id: int
    organization_name: str | None = Field(default=None, max_length=255)
    phase: PhaseType | None = None
    prefix: str | None = Field(default=None, max_length=50)


class DeleteOrgRequest(BaseModel):
    """删除组织请求体"""
    organization_id: int
