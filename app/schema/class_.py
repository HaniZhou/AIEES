from pydantic import BaseModel, Field


class ClassCreate(BaseModel):
    """班级创建请求体"""
    class_name: str = Field(max_length=255, description="班级名称")
    organization_id: int = Field(description="所属组织ID")


class ClassUpdate(BaseModel):
    """班级更新请求体（禁止修改所属组织）"""
    class_id: int
    class_name: str | None = Field(default=None, max_length=255)


class ClassRead(BaseModel):
    """班级只读模型"""
    class_id: int
    class_name: str
    model_config = {"from_attributes": True}


class DeleteClassRequest(BaseModel):
    """删除班级请求体"""
    class_id: int
