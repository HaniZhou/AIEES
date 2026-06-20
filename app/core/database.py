""" 数据库引擎与会话工厂（核心配置，独立于业务层） """
import time

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import SecretConfig, UrlConfig
from app.core.logging import SLOW_QUERY_MS, get_logger

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

#  慢查询监听（只记超过阈值的 SQL，不记参数，截断 120 字符）
db_logger = get_logger("app.core.database.slow")


def _setup_slow_query_listener():
    if SLOW_QUERY_MS <= 0:
        return

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        conn._query_start_time = time.perf_counter()
        conn._query_statement = statement

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        start = getattr(conn, "_query_start_time", None)
        if start is None:
            return
        total_ms = int((time.perf_counter() - start) * 1000)
        if total_ms >= SLOW_QUERY_MS:
            stmt = conn._query_statement or statement
            db_logger.warning("Slow query (%dms): %.120s", total_ms, stmt)


_setup_slow_query_listener()

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


async def get_session():
    """FastAPI 依赖：提供异步会话，请求结束时自动 commit/rollback"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
