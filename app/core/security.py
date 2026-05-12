""" 安全配置相关的函数和工具，例如密码哈希、JWT 生成和验证等 """
import logging

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone
from typing import Annotated, Union
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status

from app.crud.db import db_get_user_info
from app.model.schema.schema import TokenData, UserPublish, RoleType, PhaseType
from app.Config import SecretConfig

#  日志配置 
auth_logger = logging.getLogger("auth")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("fake_password")


def verify_password(plain_password, hashed_password):
    """这个方法会自动处理盐值和算法信息"""
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password):
    """ return hashed password """
    return password_hash.hash(password)


async def authenticate_user(id: str, password: str, role: RoleType) -> Union[None | UserPublish]:
    """
    函数目的：验证用户凭据（用户名是否存在 + 密码是否正确）。
             用户不存在时执行 DUMMY_HASH 验证以抵抗时序攻击。
    参数信息：
        - id: str，用户 ID。
        - password: str，明文密码。
        - role: RoleType，用户角色（决定查询哪张表）。
    返回值：UserPublish | None，验证通过返回用户公开信息，否则返回 None。
    """
    user_dict = await db_get_user_info(id, role)  # 返回的字典
    if not user_dict:
        verify_password(password, DUMMY_HASH)  # 抵抗时序攻击
        auth_logger.warning(f"Login failed: user [{id}] (role={role.value}) not found in DB")
        return None
    if not verify_password(password, user_dict.get("hashed_password")):
        auth_logger.warning(f"Login failed: user [{id}] (role={role.value}) wrong password")
        return None
    user_dict.pop("hashed_password", None)
    user_dict.pop("class_id", None)
    user_dict.pop("organization_id", None)
    return UserPublish(**user_dict)


def create_access_token(payload: dict, expires_delta: timedelta | None = None):
    """
    函数目的：生成 JWT access token。
    参数信息：
        - payload: dict，token 载荷（必须包含 id、role）。
        - expires_delta: timedelta | None，自定义过期时长，为 None 则使用默认 15 分钟。
    返回值：str，编码后的 JWT 字符串。
    """
    to_encode = payload.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SecretConfig.SECRET_KEY, algorithm=SecretConfig.ALGORITHM)
    return encoded_jwt


def verify_token_return_payload(token: Annotated[str, Depends(oauth2_scheme)]) -> TokenData:
    """
    函数目的：验证 JWT token，并返回包含学段信息的 payload。
    参数信息：- token: str, 前端携带的 Bearer Token。
    返回值：TokenData，包含 id, role 及 phase。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SecretConfig.SECRET_KEY, algorithms=[SecretConfig.ALGORITHM])
        id = payload.get("id")
        role = payload.get("role")
        phase_str = payload.get("phase")
        if role is None or id is None:
            raise credentials_exception
        # 由于 phase 现在是必选，直接解析。若遇到极早期无 phase 的 token，降级为高中
        phase = PhaseType(phase_str) if phase_str else PhaseType.senior
        return TokenData(id=id, role=role, phase=phase)
    except InvalidTokenError:
        raise credentials_exception


def require_student(payload: Annotated[TokenData, Depends(verify_token_return_payload)]) -> TokenData:
    """
    函数目的：FastAPI 依赖项，要求当前用户必须为学生角色。
    参数信息：- payload: TokenData, 由 verify_token_return_payload 解析得到。
    返回值：TokenData，验证通过后原样返回供下游使用。
    """
    if payload.role != RoleType.student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"权限不足"
        )
    return payload


def require_teacher(payload: Annotated[TokenData, Depends(verify_token_return_payload)]) -> TokenData:
    """
    函数目的：FastAPI 依赖项，要求当前用户必须为教师角色。
    参数信息：- payload: TokenData, 由 verify_token_return_payload 解析得到。
    返回值：TokenData，验证通过后原样返回供下游使用。
    """
    if payload.role != RoleType.teacher:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"权限不足"
        )
    return payload


def require_admin(payload: Annotated[TokenData, Depends(verify_token_return_payload)]) -> TokenData:
    """
    函数目的：FastAPI 依赖项，要求当前用户必须为管理员角色。
    参数信息：- payload: TokenData, 由 verify_token_return_payload 解析得到。
    返回值：TokenData，验证通过后原样返回供下游使用。
    """
    if payload.role != RoleType.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"权限不足"
        )
    return payload


def require_teacher_or_admin(payload: Annotated[TokenData, Depends(verify_token_return_payload)]) -> TokenData:
    """
    函数目的：FastAPI 依赖项，要求当前用户为教师或管理员角色。
    参数信息：- payload: TokenData, 由 verify_token_return_payload 解析得到。
    返回值：TokenData，验证通过后原样返回供下游使用。
    """
    if payload.role != RoleType.teacher and payload.role != RoleType.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"权限不足"
        )
    return payload


def require_student_or_teacher(payload: Annotated[TokenData, Depends(verify_token_return_payload)]) -> TokenData:
    """
    函数目的：FastAPI 依赖项，要求当前用户为学生或教师角色。
    参数信息：- payload: TokenData, 由 verify_token_return_payload 解析得到。
    返回值：TokenData，验证通过后原样返回供下游使用。
    """
    if payload.role != RoleType.student and payload.role != RoleType.teacher:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"权限不足"
        )
    return payload


if __name__ == "__main__":
    print(password_hash.hash("123"))
