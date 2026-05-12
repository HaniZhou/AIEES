""" Redis 异步连接池全局单例重构 """
import redis.asyncio as redis
from arq import create_pool, ArqRedis
from arq.connections import RedisSettings
from app import Config

#  1. 标准 Redis 连接池
redis_pool: redis.ConnectionPool = redis.ConnectionPool.from_url(
    f"redis://:{Config.SecretConfig.REDIS_PASSWORD}@{Config.UrlConfig.REDIS_HOST}:{Config.UrlConfig.REDIS_PORT}",
    encoding="utf-8",
    decode_responses=True
)

def get_redis() -> redis.Redis:
    """函数目的：获取标准 Redis 客户端实例，用于常规缓存操作。
    参数信息：无。
    返回值：redis.Redis 实例。
    """
    return redis.Redis(connection_pool=redis_pool)


#  2. ARQ 专用 Redis 客户端 (仅用于任务入队) 
_arq_redis: ArqRedis | None = None

async def init_arq_redis() -> ArqRedis:
    """函数目的：初始化 ARQ 专用连接池，必须在 FastAPI lifespan 启动时调用。
    参数信息：无。
    返回值：ArqRedis 实例。
    """
    global _arq_redis
    if _arq_redis is None:
        _arq_redis = await create_pool(
            RedisSettings(
                host=Config.UrlConfig.REDIS_HOST,
                port=Config.UrlConfig.REDIS_PORT,
                password=Config.SecretConfig.REDIS_PASSWORD
            )
        )
    return _arq_redis

def get_arq_redis() -> ArqRedis:
    """函数目的：获取 ARQ Redis 客户端实例，专用于 enqueue_job。
    参数信息：无。
    返回值：ArqRedis 实例。
    """
    if _arq_redis is None:
        raise RuntimeError("ARQ Redis 未初始化，请检查 FastAPI lifespan 启动顺序")
    return _arq_redis

async def close_redis_pools():
    """函数目的：优雅关闭所有 Redis 连接池，必须在 FastAPI lifespan 关闭时调用。
    参数信息：无。
    返回值：无。
    """
    global _arq_redis
    await redis_pool.aclose()
    if _arq_redis:
        await _arq_redis.close()
        _arq_redis = None
