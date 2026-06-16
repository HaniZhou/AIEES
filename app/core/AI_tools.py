""" AI related tools live here to avoid circular imports with db.py """
import asyncio

import httpx
from fastapi import HTTPException, UploadFile, File
from openai import AsyncOpenAI

from app.Config import Limit, UrlConfig, SecretConfig, Prompt
from app.core.logging import get_logger

# AI module logger（统一写入 app.log，名称格式 "app.core.AI_tools.{子模块}"）
logger = get_logger(f"{__name__}.ai")
asr_logger = get_logger(f"{__name__}.asr")

client = AsyncOpenAI(
    base_url=SecretConfig.AI_BASE_URL,
    api_key=SecretConfig.API_KAY,
    timeout=60.0,
)

# ASR client
asr_client = AsyncOpenAI(
    base_url=SecretConfig.AI_BASE_URL,
    api_key=SecretConfig.API_KAY,
    timeout=httpx.Timeout(connect=3.0, read=120.0, write=10.0, pool=5.0)
)


async def generate_gai_reply_stream(messages: list):
    completion = await client.chat.completions.create(
        model="GLM-5.1",
        messages=messages,
        temperature=0.8,
        top_p=0.8,
        max_tokens=16000,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        stream=True,
    )
    async for chunk in completion:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def generate_gai_analysis_text(system_prompt: str, user_content: str) -> str:
    """Non-streaming analysis call to LLM."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            completion = await client.chat.completions.create(
                model="GLM-5.1",
                messages=messages,
                temperature=0.8,
                top_p=0.8,
                max_tokens=20000,
                timeout=httpx.Timeout(connect=3.0, read=240.0, write=15.0, pool=5.0),
            )
            if completion.choices and completion.choices[0].message.content:
                return completion.choices[0].message.content
            return "AI分析失败：未返回有效内容"
        except Exception as e:
            if attempt == max_retries:
                raise Exception(f"AI分析重试耗尽: {str(e)}")
            logger.warning(f"API call failed, retrying ({attempt}/{max_retries}), error: {str(e)}")
            await asyncio.sleep(1 * attempt)


async def _execute_gai_analysis(task_id: int, completion_id: int, messages: list) -> None:
    # Local import to avoid circular dependency with db.py
    from app.crud.db import db_get_analysis_task_info, db_update_gai_task_analysis_result

    try:
        task_info = await db_get_analysis_task_info(task_id)
        if not task_info:
            await db_update_gai_task_analysis_result(completion_id, "AI分析失败：任务配置丢失")
            return

        class_info = (
            f"【任务描述】：{task_info.get('task_description', '未提供')}\n"
            f"【分析要求】：{task_info.get('analysis_description', '未提供')}\n"
            f"【评价标准】：{task_info.get('evaluation_criterion', '未提供')}"
        )
        system_prompt = Prompt.TEACHER_ANALYSIS_SYSTEM_PROMPT.format(class_info=class_info)

        chat_history = "\n".join([f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" for msg in messages])
        user_content = f"<INPUT_DATA>\n{chat_history}\n</INPUT_DATA>"

        analysis_text = await generate_gai_analysis_text(system_prompt, user_content)
        await db_update_gai_task_analysis_result(completion_id, analysis_text)
    except Exception as e:
        logger.error(
            f"GAI analysis execution failed, task_id={task_id}, completion_id={completion_id}, error: {str(e)}"
        )
        await db_update_gai_task_analysis_result(completion_id, "AI分析失败，请稍后重试")


async def generate_asr_reply_stream(messages: list):
    """Stream ASR recognition, with tag stripping and retries."""
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            completion = await asr_client.chat.completions.create(
                model="qwen3-asr",
                messages=messages,
                stream=True,
                extra_body={"asr_options": {"enable_itn": True}},
            )

            try:
                buffer = ""
                tag_cleared = False

                async for chunk in completion:
                    if chunk.choices and chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content

                        if not tag_cleared:
                            buffer += text
                            if ">" in buffer:
                                tag_cleared = True
                                real_text = buffer.split(">", 1)[1]
                                if real_text:
                                    yield real_text
                                buffer = ""
                            elif len(buffer) > 50:
                                tag_cleared = True
                                yield buffer
                                buffer = ""
                        else:
                            yield text

                break
            except Exception as stream_err:
                asr_logger.error(f"ASR stream interrupted during transmission: {str(stream_err)}")
                raise stream_err

        except Exception as conn_err:
            if attempt == max_retries:
                asr_logger.error(f"ASR connection failed after {max_retries} retries: {str(conn_err)}")
                raise HTTPException(status_code=502, detail="语音识别服务连接失败")
            asr_logger.warning(f"ASR connection failed, retrying ({attempt}/{max_retries}), error: {str(conn_err)}")
            await asyncio.sleep(1 * attempt)


async def validate_asr_file(file: UploadFile = File(..., description="音频文件")) -> dict:
    """Validate ASR file format and size before streaming."""
    if file.content_type not in Limit.ASR_ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的音频格式: {file.content_type}")

    contents = await file.read()

    if len(contents) > Limit.MAX_ASR_FILE_SIZE:
        raise HTTPException(status_code=400, detail="音频文件大小不能超过 40MB")

    await file.close()

    return {
        "contents": contents,
        "content_type": file.content_type,
    }