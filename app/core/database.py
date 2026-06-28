"""数据库引擎与会话工厂封装"""

import time

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import DBConfig, LogConfig
from app.core.logging import get_logger


class Database:
    def __init__(self):
        self.engine = create_async_engine(
            DBConfig.DATABASE_URL,
            echo=False,
            pool_size=DBConfig.POOL_SIZE,
            max_overflow=DBConfig.MAX_OVERFLOW,
            pool_pre_ping=DBConfig.POOL_PRE_PING,
            pool_timeout=DBConfig.POOL_TIMEOUT,
            pool_recycle=DBConfig.POOL_RECYCLE,
        )
        self._logger = get_logger("app.core.database.slow")
        self._setup_slow_query_listener()
        self.async_session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    def _setup_slow_query_listener(self):
        """注册SQL执行前后钩子，记录超过阈值的慢查询语句"""
        if LogConfig.SLOW_QUERY_MS <= 0:
            return

        @event.listens_for(self.engine.sync_engine, "before_cursor_execute")
        def _before(conn, cursor, statement, parameters, context, executemany):
            conn.info["query_start_time"] = time.perf_counter()
            conn.info["query_statement"] = statement

        @event.listens_for(self.engine.sync_engine, "after_cursor_execute")
        def _after(conn, cursor, statement, parameters, context, executemany):
            start = conn.info.pop("query_start_time", None)
            if start is None:
                return
            stmt = conn.info.pop("query_statement", None) or statement
            total_ms = int((time.perf_counter() - start) * 1000)
            if total_ms >= LogConfig.SLOW_QUERY_MS:
                self._logger.warning("Slow query (%dms): %.120s", total_ms, stmt)

    async def warmup_pool(self):
        """预热连接池，提前创建核心连接，降低首请求延迟"""
        connections = []
        try:
            for _ in range(DBConfig.POOL_SIZE):
                conn = await self.engine.connect()
                connections.append(conn)
        finally:
            for conn in connections:
                await conn.close()

    async def get_session(self):
        """异步会话生成函数，自动管理事务，异常自动回滚、正常自动提交"""
        async with self.async_session_factory() as session:
            try:
                yield session
                # Service 层不手动 commit；Service 代码只关心业务逻辑，无需操心事务提交 / 回滚的边界；
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def dispose(self):
        """销毁连接池所有连接，释放数据库资源"""
        await self.engine.dispose()


db = Database()