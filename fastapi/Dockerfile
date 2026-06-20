# syntax=docker/dockerfile:1
# ==================== Stage 1: Builder ====================
FROM python:3.14.4-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/

# 先复制依赖文件，利用 Docker 缓存加速
COPY pyproject.toml uv.lock /app/

# 用 uv 同步依赖（无 dev、冻结 lock 版本）
RUN uv sync --no-dev --frozen


# ==================== Stage 2: final ====================
FROM python:3.14.4-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 仅安装运行时需要的共享库（不需要 build-essential）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser appuser

# 从 builder 阶段复制虚拟环境和应用代码
COPY --from=builder /app/.venv /app/.venv

# 复制应用代码
COPY app/ /app/app/

EXPOSE 8000

CMD ["sh", "-c", "exec gunicorn app.main:app --workers=$(nproc) --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000  --timeout=120 --graceful-timeout=30"]

#CMD ["gunicorn", "app.main:app", "--workers", "32", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]