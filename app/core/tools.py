""" 全局工具函数都需要放置在这里，避免和业务逻辑代码耦合在一起 """
import asyncio
from app.Config import Limit, UrlConfig, SecretConfig
from fastapi import HTTPException, UploadFile
import uuid
import random
from datetime import datetime
import aiofiles
import aiofiles.os as aios
import httpx
import logging
from openai import AsyncOpenAI

#  规范落地：AI 模块日志配置 
logger = logging.getLogger("ai")
logger.setLevel(logging.WARNING)
log_file = UrlConfig.LOGS_DIR / "ai.log"
if not log_file.parent.exists():
    log_file.parent.mkdir(parents=True, exist_ok=True)
handler = logging.FileHandler(log_file, encoding="utf-8")
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [ai] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)

client = AsyncOpenAI(
    base_url=SecretConfig.AI_BASE_URL,
    api_key=SecretConfig.API_KAY,
    timeout=60.0,
)


async def generate_gai_reply_stream(messages: list):
    completion = await client.chat.completions.create(
        model="GLM-5.1",
        messages=messages,
        temperature=1,
        top_p=1,
        max_tokens=16000,
        extra_body={
            "chat_template_kwargs": {"enable_thinking": False}
        },
        stream=True,
    )
    async for chunk in completion:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def generate_gai_analysis_text(system_prompt: str, user_content: str) -> str:
    """函数目的：非流式调用大模型获取 GAI 任务的分析文本。
    参数信息：
    - system_prompt: str，系统提示词。
    - user_content: str，经过格式化拼接的学生对话历史文本。
    返回值：str，大模型生成的分析文本，若未返回有效内容则返回失败提示字符串。
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            completion = await client.chat.completions.create(
                model="GLM-5.1",
                messages=messages,
                temperature=0.9,
                top_p=1,
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


def generate_course_code(length: int = 6) -> str:
    """
    生成指定长度的课程码
    剔除了: 0(数字零), O(字母欧), 1(数字一), I(字母艾), L(字母艾欧)
    """
    # 辨识度极高的字符
    chars = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    return ''.join(random.choices(chars, k=length))



async def write_image(cover):
    if cover.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(status_code=400, detail="只能上传 jpg/png/webp 格式")

    contents = await cover.read()
    if len(contents) > Limit.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="图片大小不能超过 5MB")

    # 严格的白名单后缀提取
    suffix = cover.filename.split(".")[-1].lower()
    if suffix not in ["jpg", "jpeg", "png", "webp"]:
        raise HTTPException(status_code=400, detail="文件后缀不合法")

    new_filename = f"{uuid.uuid4().hex}.{suffix}"
    file_path = UrlConfig.COVERS_DIR / new_filename

    # 把文件写入本地磁盘
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(contents)

    db_cover_url = f"/uploads/covers/{new_filename}"

    return db_cover_url


async def remove_file(url):
    """ 删除文件
    url 例如 /cover/file.img | /pdf/file.pdf  | /video/video.mp4
    """
    normalized = _to_upload_relative_path(url)
    file_path = UrlConfig.UPLOAD_DIR / normalized.lstrip("/")

    if await aios.path.exists(file_path):
        await aios.remove(file_path)
        return True
    return False


async def write_resource(file: UploadFile) -> str:
    """处理子任务资源（视频、PDF）的上传"""
    if not file.content_type:
        raise HTTPException(status_code=400, detail="无法识别文件类型")

    contents = await file.read()

    # 分配目录与限制大小
    if file.content_type.startswith("video/"):
        if len(contents) > Limit.MAX_VIDEO_SIZE:
            raise HTTPException(status_code=413, detail="视频大小不能超过 500MB")
        sub_dir = "videos"
        allowed_suffixes = ["mp4", "mov", "avi", "mkv", "webm"]
    elif file.content_type == "application/pdf":
        if len(contents) > Limit.MAX_PDF_SIZE:
            raise HTTPException(status_code=413, detail="PDF大小不能超过 50MB")
        sub_dir = "pdfs"
        allowed_suffixes = ["pdf"]
    else:
        raise HTTPException(status_code=400, detail="仅支持上传视频(mp4等)或PDF文件")

    #后缀白名单校验
    suffix = file.filename.split(".")[-1].lower() if file.filename else ""
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail=f"不支持的文件后缀: .{suffix}")

    # 生成格式：年月日_时分秒_随机码.后缀
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}.{suffix}"

    # 确保目录存在并写入
    target_dir = UrlConfig.UPLOAD_DIR / sub_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / new_filename

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(contents)

    # 返回符合契约的相对路径
    return f"/uploads/{sub_dir}/{new_filename}"


def _is_deletable_resource_path(path: str) -> bool:
    normalized = path.lstrip("/")
    if normalized.startswith("uploads/"):
        normalized = normalized[len("uploads/"):]
    return normalized.startswith("videos/") or normalized.startswith("pdfs/")


def _to_upload_relative_path(path: str) -> str:
    normalized = path.lstrip("/")
    if normalized.startswith("uploads/"):
        normalized = normalized[len("uploads/"):]
    return normalized
