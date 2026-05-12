""" 数据库引擎与会话工厂（核心配置，独立于业务层） """
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import text
from app.Config import UrlConfig, SecretConfig

#  连接字符串构建 
_url = (
    f"postgresql+asyncpg://{SecretConfig.DB_USER}:{SecretConfig.DB_PASSWORD}"
    f"@{UrlConfig.DB_HOST}:{UrlConfig.DB_PORT}/{UrlConfig.DB_NAME}"
)

#  异步引擎初始化 
engine = create_async_engine(
    _url,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_timeout=30,
)

#  异步会话工厂 
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

#  连接池预热 
async def warmup_connection_pool() -> None:
    """函数目的：在应用启动时执行一次轻量查询，预热 asyncpg 连接池，防止首次真实请求冷启动超时。
    """
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
