from typing import Annotated

from app.core.config import Limit
from app.core.security import verify_token_return_payload
from app.schema.enums import RoleType
from app.schema.user import TokenData
from fastapi import Depends, File, HTTPException, UploadFile, status


async def validate_asr_file(file: UploadFile = File(..., description="音频文件")) -> dict:
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


def require_student(payload: Annotated[TokenData, Depends(verify_token_return_payload)]) -> TokenData:
    if payload.role != RoleType.student:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    return payload


def require_teacher(payload: Annotated[TokenData, Depends(verify_token_return_payload)]) -> TokenData:
    if payload.role != RoleType.teacher:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    return payload


def require_admin(payload: Annotated[TokenData, Depends(verify_token_return_payload)]) -> TokenData:
    if payload.role != RoleType.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    return payload


def require_teacher_or_admin(payload: Annotated[TokenData, Depends(verify_token_return_payload)]) -> TokenData:
    if payload.role != RoleType.teacher and payload.role != RoleType.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    return payload


def require_student_or_teacher(payload: Annotated[TokenData, Depends(verify_token_return_payload)]) -> TokenData:
    if payload.role != RoleType.student and payload.role != RoleType.teacher:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    return payload
