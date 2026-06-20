""" Taskiq Broker 单例 — Redis 后端 """
from taskiq_redis import ListQueueBroker

from app.core.config import SecretConfig, UrlConfig

broker = ListQueueBroker(
    f"redis://:{SecretConfig.REDIS_PASSWORD}@{UrlConfig.REDIS_HOST}:{UrlConfig.REDIS_PORT}"
)
