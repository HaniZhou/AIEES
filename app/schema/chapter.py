from pydantic import BaseModel, Field

from app.schema.enums import ResourceType


class SectionPayload(BaseModel):
    """小节更新载荷"""
    section_id: int | None = None
    section_title: str
    section_type: ResourceType
    section_order: int | None = None
    resource_path: str | None = None
    description: str


class ChapterPayload(BaseModel):
    """章节更新载荷"""
    chapter_id: int | None = None
    chapter_title: str
    chapter_order: int | None = None
    sub_tasks: list[SectionPayload] = Field(default_factory=list)


class ChapterBatchPayload(BaseModel):
    """批量更新总载荷"""
    chapters: list[ChapterPayload]


class SectionFeedbackRequest(BaseModel):
    difficulty: int = Field(ge=1, le=5)
