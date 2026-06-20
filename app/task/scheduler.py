""" TaskiqScheduler 实例 — 装配每日定时任务 """
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

from app.task.broker import broker

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[LabelScheduleSource(broker)],
)
