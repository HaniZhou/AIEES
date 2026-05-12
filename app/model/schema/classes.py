from pydantic import BaseModel

class ClassRead(BaseModel):
    """ 班级只读模型 """
    class_id: int
    class_name: str

    model_config = {"from_attributes": True}
