"""AI 客户端封装（LLM 对话 + ASR 语音识别）"""

import asyncio

import httpx
from openai import AsyncOpenAI

from app.core.config import AIConfig
from app.core.exceptions import ASRServiceError
from app.core.logging import get_logger


class LLMClient:
    def __init__(self):
        self._client = AsyncOpenAI(
            base_url=AIConfig.AI_BASE_URL,
            api_key=AIConfig.AI_API_KEY,
            timeout=60.0,
        )
        self.logger = get_logger(f"{__name__}.ai")

    async def generate_reply_stream(self, messages: list):
        """流式对话"""
        completion = await self._client.chat.completions.create( # 异步流式响应对象
            model=AIConfig.AI_MODEL_TEXT,
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

    async def generate_analysis_text(self, system_prompt: str, user_content: str) -> str:
        """一次性分析文本（含 3 次重试）"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                completion = await self._client.chat.completions.create(
                    model=AIConfig.AI_MODEL_TEXT,
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
                    raise Exception(f"AI分析重试耗尽: {str(e)}") from e
                self.logger.warning(f"API call failed, retrying ({attempt}/{max_retries}), error: {str(e)}")
                await asyncio.sleep(1 * attempt)


class ASRClient:
    def __init__(self):
        self._client = AsyncOpenAI(
            base_url=AIConfig.AI_BASE_URL,
            api_key=AIConfig.AI_API_KEY,
            timeout=httpx.Timeout(connect=3.0, read=120.0, write=10.0, pool=5.0),
        )
        self.logger = get_logger(f"{__name__}.asr")

    async def generate_reply_stream(self, messages: list):
        """流式 ASR 识别（含 3 次重试）"""
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                completion = await self._client.chat.completions.create(
                    model=AIConfig.AI_MODEL_ASR,
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
                    self.logger.error(f"ASR stream interrupted during transmission: {str(stream_err)}")
                    raise stream_err

            except Exception as conn_err:
                if attempt == max_retries:
                    self.logger.error(f"ASR connection failed after {max_retries} retries: {str(conn_err)}")
                    raise ASRServiceError("语音识别服务连接失败", original_error=conn_err) from conn_err
                self.logger.warning(f"ASR connection failed, retrying ({attempt}/{max_retries}), error: {str(conn_err)}")
                await asyncio.sleep(1 * attempt)


llm = LLMClient()
asr = ASRClient()
