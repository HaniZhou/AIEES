"""服务相关接口，包含资源上传和与GAI的对话接口"""
import base64
from collections.abc import AsyncIterable
from typing import Annotated

from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.api.dependencies import require_student, require_teacher, validate_asr_file
from app.common.response import response_success
from app.common.tools import write_resource
from app.core.ai_client import llm, asr
from app.core.config import Limit
from app.core.prompts import Prompt
from app.core.rate_limiter import rate_limiter
from app.core.security import verify_token_return_payload
from app.schema.chat import ChatRequest
from app.schema.enums import ScenarioType
from app.schema.user import TokenData
from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile

router = APIRouter()
#  接口实现
@router.post("/resource")
async def upload_resource(
    payload: Annotated[TokenData, Depends(verify_token_return_payload)],
    file: UploadFile = File(..., description="资源文件 (视频/PDF)"),
) -> JSONResponse:
    """独立的文件上传接口"""
    path = await write_resource(file)
    return response_success({"path": path})
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
        async for text_chunk in llm.generate_reply_stream(messages):
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
        async for text_chunk in llm.generate_reply_stream(messages):
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
        async for text_chunk in llm.generate_reply_stream(messages):
            yield ServerSentEvent(data={"content": text_chunk}, event="token")
            if await request.is_disconnected():
                client_disconnected = True
                break
    except Exception as e:
        yield ServerSentEvent(data={"error": str(e)}, event="error")

    if not client_disconnected:
        yield ServerSentEvent(data="[DONE]", event="done")



@router.post("/asr", response_class=EventSourceResponse)
async def speech_to_text_stream(
        request: Request,
        # 关键修复：将文件校验作为依赖注入，确保在流式响应建立前拦截 400 错误
        asr_file_data: dict = Depends(validate_asr_file),
        token_data: TokenData = Depends(rate_limiter.asr_rate_limit)
) -> AsyncIterable[ServerSentEvent]:
    """流式音频文件上传识别接口"""

    # 从依赖返回值中解包数据
    contents = asr_file_data["contents"]
    content_type = asr_file_data["content_type"]

    # 构造 Data URI 和 Messages
    data_uri = base64.b64encode(contents).decode('utf-8')
    audio_format = Limit.ASR_ALLOWED_CONTENT_TYPES.get(content_type, "mp3")

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": data_uri,
                        "format": audio_format
                    }
                }
            ]
        }
    ]

    client_disconnected = False

    try:
        async for text_chunk in asr.generate_reply_stream(messages):
            yield ServerSentEvent(data={"content": text_chunk}, event="token")
            if await request.is_disconnected():
                client_disconnected = True
                break
    except HTTPException:
        # 拦截连接阶段重试耗尽抛出的 502 异常，转为 SSE error 事件
        yield ServerSentEvent(data={"error": "语音识别服务暂时不可用"}, event="error")
    except Exception as e:
        # 拦截推流中途断开或其他未预料异常，转为 SSE error 事件
        asr.logger.error(f"Unexpected error during ASR streaming: {str(e)}")
        yield ServerSentEvent(data={"error": "语音识别中断，请重试"}, event="error")

    if not client_disconnected:
        yield ServerSentEvent(data="[DONE]", event="done")
