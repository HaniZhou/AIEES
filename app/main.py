from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from app.api.v1 import auth, course, classes, services, student, organizatoin, admin
from app.Config import UrlConfig, CORSConfig

# 导入异常处理器
from app.core.exceptions import (
    pydantic_validation_exception_handler,
    app_business_exception_handler,
    http_exception_handler,
    global_system_exception_handler
)
# 导入业务异常类
from app.crud.db import AppBusinessException
# 导入连接池预热
from app.core.database import warmup_connection_pool, engine
# 导入 Redis 连接池关闭
from app.core.redis_pool import close_redis_pools, init_arq_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ==================== 启动阶段 ====================
    try:
        UrlConfig.init_directories()
    except Exception as e:
        print(f"无法创建必要的目录，请检查权限！详情: {e}")
        raise

    # 预热连接池，确保 asyncpg 连接就绪
    await warmup_connection_pool()

    # 执行建表与灌初始数据
    from app.crud.db import create_bd_and_table
    await create_bd_and_table()

    # 初始化 ARQ 任务队列专用 Redis 连接池
    await init_arq_redis()

    yield

    # ==================== 关闭阶段 ====================
    # 关闭数据库连接池
    await engine.dispose()
    # 关闭 Redis 双池
    await close_redis_pools()


app = FastAPI(lifespan=lifespan)

# ==================== 注入全局拦截器 ====================
# 1. 参数校验拦截器
app.add_exception_handler(RequestValidationError, pydantic_validation_exception_handler)
# 2. 业务异常拦截器
app.add_exception_handler(AppBusinessException, app_business_exception_handler)
# 3. HTTP 异常拦截器
app.add_exception_handler(HTTPException, http_exception_handler)
# 4. 兜底系统异常拦截器
app.add_exception_handler(Exception, global_system_exception_handler)

# ==================== 中间件与路由 ====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORSConfig.cors_allow_origins,
    allow_credentials=True,
    allow_methods=CORSConfig.cors_allow_methods,
    allow_headers=CORSConfig.cors_allow_headers,
    max_age=600,
)

app.include_router(auth.router, prefix="/api/auth")
app.include_router(course.router, prefix="/api/course")
app.include_router(classes.router, prefix="/api/classes")
app.include_router(services.router, prefix="/api/services", tags=["services"])
app.include_router(student.router, prefix="/api/student", tags=["student"])
app.include_router(organizatoin.router, prefix="/api/organization")

app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
