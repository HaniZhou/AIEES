"""安全配置相关的函数和工具，例如密码哈希、JWT 生成和验证等"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import SecretConfig
from app.core.logging import get_logger
from app.schema.enums import PhaseType
from app.schema.user import TokenData
from fastapi import Depends, HTTPException, status

auth_logger = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("fake_password")


def verify_password(plain_password, hashed_password):
    """这个方法会自动处理盐值和算法信息"""
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password):
    """return hashed password"""
    return password_hash.hash(password)


def create_access_token(payload: dict, expires_delta: timedelta | None = None):
    """
    函数目的：生成 JWT access token。
    参数信息：
        - payload: dict，token 载荷（必须包含 id、role）。
        - expires_delta: timedelta | None，自定义过期时长，为 None 则使用默认 15 分钟。
    返回值：str，编码后的 JWT 字符串。
    """
    to_encode = payload.copy()
    expire = datetime.now(UTC) + expires_delta if expires_delta else datetime.now(UTC) + timedelta(minutes=15)
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


if __name__ == "__main__":
    print(password_hash.hash("123"))
