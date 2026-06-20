""" 全局工具函数都需要放置在这里，避免和业务逻辑代码耦合在一起 """
import random
import uuid
from datetime import datetime

import aiofiles
import aiofiles.os as aios

from app.core.exceptions import AppBusinessException
from app.core.config import Limit, UrlConfig
from fastapi import UploadFile


def generate_course_code(length: int = 6) -> str:
    """
    生成指定长度的课程码
    剔除了: 0(数字零), O(字母欧), 1(数字一), I(字母艾), L(字母艾欧)
    """
    chars = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    return "".join(random.choices(chars, k=length))


async def write_image(cover):
    if cover.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise AppBusinessException(400, "只能上传 jpg/png/webp 格式")

    contents = await cover.read()
    if len(contents) > Limit.MAX_FILE_SIZE:
        raise AppBusinessException(413, "图片大小不能超过 5MB")

    suffix = cover.filename.split(".")[-1].lower()
    if suffix not in ["jpg", "jpeg", "png", "webp"]:
        raise AppBusinessException(400, "文件后缀不合法")

    new_filename = f"{uuid.uuid4().hex}.{suffix}"
    file_path = UrlConfig.COVERS_DIR / new_filename

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(contents)

    return f"/uploads/covers/{new_filename}"


async def remove_file(url):
    """ 删除文件: url 例如 /cover/file.img | /pdf/file.pdf  | /video/video.mp4 """
    normalized = to_upload_relative_path(url)
    file_path = UrlConfig.UPLOAD_DIR / normalized.lstrip("/")

    if await aios.path.exists(file_path):
        await aios.remove(file_path)
        return True
    return False


async def write_resource(file: UploadFile) -> str:
    if not file.content_type:
        raise AppBusinessException(400, "无法识别文件类型")

    contents = await file.read()

    if file.content_type.startswith("video/"):
        if len(contents) > Limit.MAX_VIDEO_SIZE:
            raise AppBusinessException(413, "视频大小不能超过 500MB")
        sub_dir = "videos"
        allowed_suffixes = ["mp4", "mov", "avi", "mkv", "webm"]
    elif file.content_type == "application/pdf":
        if len(contents) > Limit.MAX_PDF_SIZE:
            raise AppBusinessException(413, "PDF大小不能超过 50MB")
        sub_dir = "pdfs"
        allowed_suffixes = ["pdf"]
    else:
        raise AppBusinessException(400, "仅支持上传视频(mp4等)或PDF文件")

    suffix = file.filename.split(".")[-1].lower() if file.filename else ""
    if suffix not in allowed_suffixes:
        raise AppBusinessException(400, f"不支持的文件后缀: .{suffix}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}.{suffix}"

    target_dir = UrlConfig.UPLOAD_DIR / sub_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / new_filename

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(contents)

    return f"/uploads/{sub_dir}/{new_filename}"


def is_deletable_resource_path(path: str) -> bool:
    normalized = path.lstrip("/")
    if normalized.startswith("uploads/"):
        normalized = normalized[len("uploads/"):]
    return normalized.startswith("videos/") or normalized.startswith("pdfs/")


def to_upload_relative_path(path: str) -> str:
    normalized = path.lstrip("/")
    if normalized.startswith("uploads/"):
        normalized = normalized[len("uploads/"):]
    return normalized
