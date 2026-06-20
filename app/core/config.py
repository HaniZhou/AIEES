""" 全局常量配置 """
import os
from pathlib import Path


class CORSConfig:
    # 从环境变量读取，多个 origin 用逗号分隔
    cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    cors_allow_origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()]

    cors_allow_methods = ["GET",
                          "POST",
                          "OPTIONS",
                          "PUT",
                          "DELETE",
                          "PATCH",
                          ]
    cors_allow_headers = ["Content-Type",
                          "Authorization",
                          "Accept",
                          "Origin",
                          "X-Requested-With",
                           "X-Request-Id", ]


class SecretConfig:
    # JTW 加密
    SECRET_KEY = os.getenv("SECRET_KEY", None)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Redis配置
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", None)

    # 数据库配置
    DB_USER: str = os.getenv("DB_USER", None)
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", None)
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", None)
    ADMIN_NAME: str = os.getenv("ADMIN_NAME", None)

    # AI 配置
    AI_BASE_URL = os.getenv("BASE_URL", None)
    API_KEY = os.getenv("API_KEY", None)


class UrlConfig:
    # Docker 环境直接使用绝对路径，避免 Gunicorn Fork 时的路径偏移问题
    BASE_DIR: Path = Path("/app")
    ROOT_DIR: Path = Path("/app")

    STATIC_DIR: Path = Path("/app/static")
    UPLOAD_DIR: Path = Path("/app/static/uploads")
    COVERS_DIR: Path = Path("/app/static/uploads/covers")
    PDF_DIR: Path = Path("/app/static/uploads/pdfs")
    VIDEO_DIR: Path = Path("/app/static/uploads/videos")
    # Redis 配置
    REDIS_HOST: str = os.getenv("REDIS_HOST", None)
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", None))

    # 数据库配置
    DB_HOST: str = os.getenv("DB_HOST", None)
    DB_PORT: int = int(os.getenv("DB_PORT", None))
    DB_NAME: str = os.getenv("DB_NAME", None)

    @classmethod
    def init_directories(cls):
        """初始化所有必要的目录"""
        for dir_path in [cls.STATIC_DIR, cls.UPLOAD_DIR,
                         cls.COVERS_DIR, cls.PDF_DIR, cls.VIDEO_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)

    # 文件路径
    DATABASE_PATH: Path = ROOT_DIR / "database.db"

    # 验证路径
    @classmethod
    def validate(cls):
        """验证关键路径"""
        if not cls.DATABASE_PATH.exists():
            print(f"数据库文件不存在: {cls.DATABASE_PATH}")
        return True


class Limit:
    MAX_VIDEO_SIZE: int = 500 * 1024 * 1024  # 500MB
    MAX_PDF_SIZE: int = 50 * 1024 * 1024  # 50MB
    MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5MB，封面图限制

    # ASR 限制
    MAX_ASR_FILE_SIZE: int = 40 * 1024 * 1024  # 40MB
    ASR_ALLOWED_CONTENT_TYPES = {
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/x-mpeg": "mp3",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/webm": "webm",
        "audio/ogg": "ogg"
    }


class AuthSecurityConfig:
    """ 登录安全与验证码策略配置 """
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


