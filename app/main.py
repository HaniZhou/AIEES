from contextlib import asynccontextmanager

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.classes import router as classes_router
from app.api.v1.course import router as course_router
from app.api.v1.organization import router as organization_router
from app.api.v1.service import router as services_router
from app.api.v1.student import router as student_router
from app.core.config import CORSConfig, UrlConfig

# 导入连接池预热
from app.core.database import db

# 导入异常处理器
# 导入业务异常类
from app.core.exceptions import (
    AppBusinessException,
    app_business_exception_handler,
    global_system_exception_handler,
    http_exception_handler,
    pydantic_validation_exception_handler,
)

# 导入日志配置
from app.core.logging import configure_logging

# 导入中间件
from app.core.middleware import RequestIDMiddleware

# 导入 Redis 连接池关闭
from app.core.redis import redis_client
from fastapi import FastAPI, HTTPException


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ==================== 启动阶段 ====================
    # 日志配置必须在最前面
    configure_logging()

    try:
        print("正在创建必要的目录...")
        UrlConfig.init_directories()
    except Exception as e:
        print(f"无法创建必要的目录，请检查权限！详情: {e}")
        raise

    # 预热连接池，确保 asyncpg 连接就绪
    await db.warmup_pool()

    yield

    # ==================== 关闭阶段 ====================
    # 关闭数据库连接池
    await db.dispose()
    # 关闭 Redis 双池
    await redis_client.close()


app = FastAPI(lifespan=lifespan)

# 关联 ID Middleware（必须放在最外层，在路由处理之前）
app.add_middleware(RequestIDMiddleware)

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
    allow_origins=CORSConfig.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=CORSConfig.CORS_ALLOW_METHODS_LIST,
    allow_headers=CORSConfig.CORS_ALLOW_HEADERS_LIST,
    max_age=600,
)

app.include_router(auth_router, prefix="/api/auth")
app.include_router(course_router, prefix="/api/course")
app.include_router(classes_router, prefix="/api/classes")
app.include_router(services_router, prefix="/api/service", tags=["service"])
app.include_router(student_router, prefix="/api/student", tags=["student"])
app.include_router(organization_router, prefix="/api/organization")

app.include_router(admin_router, prefix="/api/admin", tags=["admin"])


@app.get("/health")
async def health():
    """健康检查端点（用于 Docker Compose healthcheck / K8s liveness probe）。"""
    from sqlmodel import select

    checks = {"status": "healthy", "db": False, "redis": False}

    # 检查 PostgreSQL
    try:
        async with db.async_session_factory() as session:
            await session.exec(select(1))
        checks["db"] = True
    except Exception:
        checks["status"] = "degraded"

    # 检查 Redis
    try:
        redis = redis_client.get_client()
        await redis.ping()
        checks["redis"] = True
    except Exception:
        checks["status"] = "degraded"

    status_code = 200 if checks["status"] == "healthy" else 503
    return JSONResponse(content=checks, status_code=status_code)
