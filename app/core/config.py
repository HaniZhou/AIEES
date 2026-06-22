from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CORSConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "OPTIONS", "PUT", "DELETE", "PATCH"]
    CORS_ALLOW_HEADERS: list[str] = [
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-Request-Id",
    ]

    @computed_field
    def CORS_ALLOW_ORIGINS(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


CORSConfig = CORSConfig()


class SecretConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # JTW 加密
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    # 后端管理员
    ADMIN_NAME: str
    ADMIN_PASSWORD: str


SecretConfig = SecretConfig()


class UrlConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    BASE_DIR: Path = Path("/app")
    ROOT_DIR: Path = Path("/app")
    STATIC_DIR: Path = Path("/app/static")
    UPLOAD_DIR: Path = Path("/app/static/uploads")
    COVERS_DIR: Path = Path("/app/static/uploads/covers")
    PDF_DIR: Path = Path("/app/static/uploads/pdfs")
    VIDEO_DIR: Path = Path("/app/static/uploads/videos")

    def init_directories(self):
        for dir_path in [self.STATIC_DIR,self.UPLOAD_DIR, self.COVERS_DIR, self.PDF_DIR, self.VIDEO_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)


UrlConfig = UrlConfig()


class Limit(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    MAX_VIDEO_SIZE: int = 524_288_000
    MAX_PDF_SIZE: int = 52_428_800
    MAX_FILE_SIZE: int = 5_242_880
    MAX_ASR_FILE_SIZE: int = 41_943_040
    ASR_ALLOWED_CONTENT_TYPES: dict[str, str] = {
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/x-mpeg": "mp3",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/webm": "webm",
        "audio/ogg": "ogg",
    }


Limit = Limit()


class AIConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    AI_BASE_URL: str
    AI_MODEL_TEXT: str
    AI_MODEL_ASR: str
    AI_API_KEY: str


AIConfig = AIConfig()


class DBConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    @computed_field
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{DBConfig.DB_USER}:{DBConfig.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


DBConfig = DBConfig()


class RedisConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    @computed_field
    def REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}"


RedisConfig = RedisConfig()


class LogConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    LOG_LEVEL: str = "INFO"
    SLOW_QUERY_MS: int = 500


LogConfig = LogConfig()


class AuthSecurityConfig(BaseSettings):
    """登录安全与验证码策略配置"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 验证码有效期（秒）
    CAPTCHA_TTL: int = 300
    # 登录失败计数时间窗口（秒），超过此时间失败次数自动清零
    LOGIN_FAIL_COUNT_TTL: int = 180
    # 账号锁定时长（秒）
    LOGIN_LOCK_TTL: int = 900
    # 触发强制要求验证码的连续失败次数阈值
    FAIL_THRESHOLD_CAPTCHA: int = 3
    # 触发直接锁定账号的连续失败次数阈值
    FAIL_THRESHOLD_LOCK: int = 10


AuthSecurityConfig = AuthSecurityConfig()
