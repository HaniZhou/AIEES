# syntax=docker/dockerfile:1
FROM python:3.14.4-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 设置工作目录
WORKDIR /app

# 安装必要的系统依赖 (针对 asyncpg 和基础编译构建通常需要这些)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件并安装，利用 Docker 缓存加速构建
COPY requirements.txt /app/

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/ && \
    pip config set install.trusted-host pypi.tuna.tsinghua.edu.cn

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制整个项目代码到工作区
COPY . /app/

# 设置暴露的端口（供 FastAPI 使用）
EXPOSE 8000

# 默认启动命令（启动 FastAPI 服务）
 CMD ["gunicorn", "app.main:app", "--workers", "32", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]