from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):
    role: str = Field(description="角色: user / assistant")
    content: str = Field(description="消息内容")


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(description="对话历史")

    @model_validator(mode='after')
    def block_system_role_injection(self) -> ChatRequest:
        if any(msg.role.lower() == "system" for msg in self.messages):
            raise ValueError("安全拦截：禁止在对话历史中传递系统提示词")
        return self
