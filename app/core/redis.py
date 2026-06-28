"""Redis 异步连接池全局单例"""

import redis.asyncio as redis

from app.core.config import RedisConfig


class RedisClient:
    def __init__(self):
        self._pool = redis.ConnectionPool.from_url(
            RedisConfig.REDIS_URL,
            encoding="utf-8",
            decode_responses=True, # 自动回复解码
            max_connections=100,  # 最大连接数
            socket_timeout=5,  # 命令超时时间（秒）
            socket_keepalive=True,  # 开启TCP保活
        )

    def get_client(self) -> redis.Redis:
        """获取 Redis 客户端实例，从连接池中分配"""
        return redis.Redis(connection_pool=self._pool)

    async def close(self):
        """关闭连接池，释放 Redis 连接资源"""
        await self._pool.aclose()


redis_client = RedisClient()
