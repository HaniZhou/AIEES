""" Taskiq Broker 单例 — Redis 后端 """
from taskiq_redis import ListQueueBroker

from app.core.config import RedisConfig

broker = ListQueueBroker(RedisConfig.REDIS_URL)
