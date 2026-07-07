# 触发任务子模块的统一注册
import app.task.job  # noqa: F401 — side-effect import for taskiq registration
from app.task.scheduler import scheduler  # noqa: F401 — side-effect import for taskiq scheduler
