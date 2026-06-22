""" Redis 异步连接池全局单例（仅保留标准 Redis 连接池） """
import redis.asyncio as redis

from app.core.config import RedisConfig

redis_pool: redis.ConnectionPool = redis.ConnectionPool.from_url(
    RedisConfig.REDIS_URL,
    encoding="utf-8",
    decode_responses=True
)

def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=redis_pool)

async def close_redis_pools():
    await redis_pool.aclose()
