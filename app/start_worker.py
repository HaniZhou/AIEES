""" 启动 ARQ Worker 的独立脚本，在终端运行: python start_worker.py """
import asyncio
from app.core.logging import configure_logging
from app.core.arq_jobs import WorkerSettings

if __name__ == "__main__":
    configure_logging()
    # 运行监听任务队列的 Worker
    WorkerSettings().watch()