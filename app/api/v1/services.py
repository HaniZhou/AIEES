"""服务相关接口，包含资源上传和与GAI的对话接口"""
from fastapi import APIRouter, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from fastapi import status, Request
from collections.abc import AsyncIterable
from typing import Annotated
from fastapi import Header
from fastapi.sse import EventSourceResponse, ServerSentEvent
from app.core.tools import write_resource, generate_gai_reply_stream
from app.core.security import verify_token_return_payload, require_teacher, require_student
from app.model.schema.schema import TokenData, ChatRequest, PhaseType, ScenarioType
from app.Config import Prompt
router = APIRouter()
#  统一响应构造器 
def _success(data=None) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"code": 200, "data": data if data is not None else {}}
    )
#  接口实现 
@router.post("/resource")
async def upload_resource(
    payload: Annotated[TokenData, Depends(verify_token_return_payload)],
    file: UploadFile = File(..., description="资源文件 (视频/PDF)"),
) -> JSONResponse:
    """独立的文件上传接口"""
    path = await write_resource(file)
    return _success({"path": path})
@router.post("/chat/stream/student", response_class=EventSourceResponse)
async def chat_stream_student(
    request: Request,
    body: ChatRequest,
    token_data: Annotated[TokenData, Depends(require_student)],
    last_event_id: Annotated[int | None, Header()] = None,
) -> AsyncIterable[ServerSentEvent]:
    """学生流式对话接口，根据学段动态加载 Prompt"""
    messages = [msg.model_dump() for msg in body.messages]

    # 调用 Config 中的动态拼接函数，传入普通解题场景
    system_prompt = Prompt.get_student_prompt(token_data.phase, ScenarioType.normal)

    if not messages or messages[0]["role"] != "system":
        messages.insert(0, {"role": "system", "content": system_prompt})
    else:
        messages[0]["content"] = system_prompt
    client_disconnected = False
    try:
        async for text_chunk in generate_gai_reply_stream(messages):
            yield ServerSentEvent(data={"content": text_chunk}, event="token")
            if await request.is_disconnected():
                client_disconnected = True
                break
    except Exception as e:
        yield ServerSentEvent(data={"error": str(e)}, event="error")

    if not client_disconnected:
        yield ServerSentEvent(data="[DONE]", event="done")
@router.post("/chat/stream/teacher", response_class=EventSourceResponse)
async def chat_stream_teacher(
    request: Request,
    body: ChatRequest,
    token_data: Annotated[TokenData, Depends(require_teacher)],
    last_event_id: Annotated[int | None, Header()] = None,
) -> AsyncIterable[ServerSentEvent]:
    """教师流式对话接口"""
    messages = [msg.model_dump() for msg in body.messages]

    # 直接调用严谨专家版 Prompt
    if not messages or messages[0]["role"] != "system":
        messages.insert(0, {"role": "system", "content": Prompt.TEACHER_SYSTEM_PROMPT})
    else:
        messages[0]["content"] = Prompt.TEACHER_SYSTEM_PROMPT

    client_disconnected = False
    try:
        async for text_chunk in generate_gai_reply_stream(messages):
            yield ServerSentEvent(data={"content": text_chunk}, event="token")
            if await request.is_disconnected():
                client_disconnected = True
                break
    except Exception as e:
        yield ServerSentEvent(data={"error": str(e)}, event="error")

    if not client_disconnected:
        yield ServerSentEvent(data="[DONE]", event="done")
@router.post("/chat/stream/gai_chat", response_class=EventSourceResponse)
async def chat_stream_gai(
    request: Request,
    body: ChatRequest,
    token_data: Annotated[TokenData, Depends(require_student)],
    last_event_id: Annotated[int | None, Header()] = None,
) -> AsyncIterable[ServerSentEvent]:
    """学生 GAI 探究式对话接口，根据学段动态加载探究 Prompt"""
    messages = [msg.model_dump() for msg in body.messages]

    # 调用 Config 中的动态拼接函数，传入 AGI 探究场景
    system_prompt = Prompt.get_student_prompt(token_data.phase, ScenarioType.agi)

    if not messages or messages[0]["role"] != "system":
        messages.insert(0, {"role": "system", "content": system_prompt})
    else:
        messages[0]["content"] = system_prompt
    client_disconnected = False
    try:
        async for text_chunk in generate_gai_reply_stream(messages):
            yield ServerSentEvent(data={"content": text_chunk}, event="token")
            if await request.is_disconnected():
                client_disconnected = True
                break
    except Exception as e:
        yield ServerSentEvent(data={"error": str(e)}, event="error")

    if not client_disconnected:
        yield ServerSentEvent(data="[DONE]", event="done")