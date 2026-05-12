# AIEES — GAI 科学素养平台

> **AI-Enhanced Education System** — 基于生成式人工智能（GAI）的互动式科学素养教学平台。

前端仓库地址：[source_code_front](./source_code_front)
后端仓库地址：[app](./app)

---

## 目录

- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [环境要求](#环境要求)
- [快速开始（Docker Compose 一键部署）](#快速开始docker-compose-一键部署)
- [手动部署（不依赖 Docker）](#手动部署不依赖-docker)
  - [1. 后端启动](#1-后端启动)
  - [2. 前端构建与部署](#2-前端构建与部署)
  - [3. Nginx 配置](#3-nginx-配置)
- [前端重新打包（Vue 构建指南）](#前端重新打包vue-构建指南)
- [环境变量说明](#环境变量说明)
- [目录结构](#目录结构)
- [常见问题](#常见问题)

---

## 系统架构

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│              │      │              │      │              │
│  浏览器/客户端│─────▶│   Nginx       │─────▶│  FastAPI     │
│  (Vue SPA)   │      │  (反向代理 +   │      │  (API 服务)   │
│              │◀─────│   静态文件)    │◀─────│              │
└──────────────┘      └──────────────┘      └──────┬───────┘
                                                    │
                    ┌───────────────────────────────┼───────────────┐
                    │                               │               │
                    ▼                               ▼               ▼
            ┌──────────────┐              ┌──────────────┐
            │  PostgreSQL  │              │    Redis      │
            │  (主数据库)   │              │  (缓存/队列)   │
            └──────────────┘              └──────┬───────┘
                                                 │
                                         ┌───────▼───────┐
                                         │  ARQ Worker    │
                                         │  (异步任务队列)  │
                                         │  AI 评分/分析   │
                                         └───────────────┘
```

系统由 **5 个 Docker 容器** 组成：
| 服务 | 容器名 | 说明 |
|------|--------|------|
| `db` | `psql` | PostgreSQL 18 数据库 |
| `redis` | `redis_server` | Redis 8 缓存与任务队列 |
| `api` | `fastapi` | FastAPI 后端 API 服务 (占用 8000) |
| `worker` | `arq_worker` | ARQ 异步任务 Worker（AI 评分、学情分析） |
| `nginx` | `nginx` | Nginx 反向代理 + 前端静态文件服务 (占用 80) |

---

## 技术栈

### 后端 (app/)
- **框架**: Python 3.14, FastAPI, Uvicorn/Gunicorn
- **ORM**: SQLModel + SQLAlchemy + asyncpg
- **数据库**: PostgreSQL 18
- **缓存/队列**: Redis 8 + ARQ
- **AI 集成**: OpenAI API (兼容接口)
- **认证**: JWT (PyJWT)
- **文件处理**: Pillow, python-multipart, aiofiles

### 前端 (source_code_front/)
- **框架**: Vue 3 (Composition API)
- **构建工具**: Vite 8
- **UI 组件库**: Vant 4 (移动端优先)
- **状态管理**: Pinia
- **路由**: Vue Router 4
- **图表**: ECharts 6
- **HTTP**: Axios
- **Markdown**: markdown-it, katex, turndown
- **文档预览**: PDF.js, mammoth (Word)

---

## 环境要求

| 依赖 | 版本要求 |
|------|----------|
| Docker | >= 24.0 |
| Docker Compose | >= 2.20 (V2) |
| (手动部署) Python | >= 3.12 |
| (手动部署) Node.js | >= 20.19 或 >= 22.12 |
| (手动部署) pnpm/npm | 最新版 |
| 磁盘空间 | >= 5GB (含 Docker 镜像) |
| 内存 | >= 4GB (推荐 8GB) |

---

## 快速开始（Docker Compose 一键部署）

### 1. 克隆项目

```bash
git clone https://github.com/HaniZhou/AIEES.git
cd AIEES
```

### 2. 构建前端

```bash
cd source_code_front
npm install
# 编辑 .env.production，将 API 地址设为 Nginx 代理路径
# VITE_API_BASE_URL=http://localhost/api
# VITE_RESOURCE_BASE_URL=http://localhost/api
npm run build
mkdir -p ../frontend/dist
cp -r dist/* ../frontend/dist/
cd ..
```

> 如需自定义后端地址，构建前编辑 `source_code_front/.env.production` 中的 `VITE_API_BASE_URL`。

### 3. 配置环境变量

所有环境变量已在 `docker-compose.yml` 中预设了默认值。如需修改数据库密码、Redis 密码等敏感信息，编辑 `docker-compose.yml` 中对应服务的 `environment` 段。

### 4. 配置 AI 接口密钥

后端已通过环境变量 `BASE_API` 和 `API_KEY` 接入 AI 客户端（参见 `app/Config.py` 与 `app/core/tools.py`）。在 `docker-compose.yml` 的 `api` 和 `worker` 服务中添加：

```yaml
environment:
  - BASE_API=https://api.openai.com/v1
  - API_KEY=sk-your-key-here
```

支持的 AI 功能：
- 学生端苏格拉底式 AI 导师对话
- 主观题自动评分
- 学情分析报告生成
- 教师端教学策略建议

### 5. 启动所有服务

```bash
docker compose up -d
```

首次启动会构建后端镜像，耗时约 5-10 分钟。

### 6. 验证部署

- **前端页面**: http://localhost
- **后端 API**: http://localhost/api/ （通过 Nginx 代理）
- **Swagger 文档**: 默认不对外暴露，如需访问，在 `docker-compose.yml` 的 `api` 服务中添加 `ports: - "8000:8000"`，然后访问 `http://localhost:8000/docs`

> ⚠️ **首次登录**：系统启动后默认已创建管理员账号。打开前端页面，点击「管理员登录」，使用以下凭据登录：
> - **账号**: `Admin`
> - **密码**: `Default_value`
> 
> **请尽快修改默认密码！** 默认密码硬编码在 `app/crud/db.py` 的 `init_mock_data()` 函数中，部署前可修改该文件中的 `"Default_value"` 为你自己的密码，重新构建镜像后生效。也可登录后进入系统管理后台手动修改密码。

### 7. 查看日志

```bash
# 查看所有服务日志
docker compose logs -f

# 查看特定服务
docker compose logs -f api
docker compose logs -f worker
```

### 8. 停止服务

```bash
docker compose down
```

如需同时删除数据卷（清空数据库和 Redis 数据）：

```bash
docker compose down -v
```

---

## 手动部署（不依赖 Docker）

### 1. 后端启动

#### 1.1 安装系统依赖

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv postgresql redis-server
```

**CentOS/RHEL:**
```bash
sudo yum install python3 python3-pip postgresql-server redis
```

#### 1.2 配置 PostgreSQL

```bash
# 创建数据库和用户
sudo -u postgres psql
CREATE DATABASE postgres;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE postgres TO postgres;
\q
```

#### 1.3 配置 Redis

```bash
# 编辑 redis.conf，设置密码
sudo sed -i 's/# requirepass foobared/requirepass redis123/' /etc/redis/redis.conf
sudo systemctl restart redis
```

#### 1.4 安装 Python 依赖

```bash
cd AIEES
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### 1.5 设置环境变量

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=postgres
export DB_USER=postgres
export DB_PASSWORD=postgres
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_PASSWORD=redis123
export SECRET_KEY=your-strong-secret-key
```

> **AI 配置**: 添加 `export BASE_API=https://api.openai.com/v1` 和 `export API_KEY=sk-your-key-here`（参考上方的 [配置 AI 接口密钥] 章节）。

#### 1.6 启动 FastAPI 服务

```bash
# 开发模式（热重载）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 生产模式（推荐使用 Gunicorn）
gunicorn app.main:app --workers 32 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

#### 1.7 启动 ARQ Worker（用于异步任务）

```bash
arq app.core.arq_jobs.WorkerSettings
```

---

### 2. 前端构建与部署

参见 [前端重新打包](#前端重新打包vue-构建指南) 章节。

---

### 3. Nginx 配置

```bash
# 安装 Nginx
sudo apt-get install -y nginx

# 复制 nginx.conf
sudo cp nginx.conf /etc/nginx/nginx.conf

# 确保前端静态文件目录存在
sudo mkdir -p /var/www/frontend
sudo cp -r frontend/dist/* /var/www/frontend/

# 确保上传目录存在
sudo mkdir -p /var/www/static/uploads
sudo chmod -R 755 /var/www/static

# 重启 Nginx
sudo systemctl restart nginx
```

> **重要**: 如果后端不在本机，需要修改 `nginx.conf` 中的 `proxy_pass http://api:8000;` 为实际后端地址。

---

## 前端重新打包（Vue 构建指南）

当您修改了前端代码后，需要重新构建才能生效。

### 构建步骤

```bash
# 1. 进入前端源码目录
cd source_code_front

# 2. 安装依赖（首次或依赖有变更时）
npm install
# 或使用 pnpm（推荐）
pnpm install

# 3. 修改 API 地址（如需）
# 编辑 .env.production 文件
# VITE_API_BASE_URL=http://你的服务器IP:8000/api
# VITE_RESOURCE_BASE_URL=http://你的服务器IP:8000/api

# 4. 构建生产版本
npm run build

# 5. 将构建产物复制到 Nginx 静态目录
# Docker 部署方式：
cp -r dist/* ../frontend/dist/
# 或在项目根目录执行：docker compose restart nginx

# 手动部署方式：
sudo cp -r dist/* /var/www/frontend/
sudo systemctl restart nginx
```

### 构建产物说明

构建完成后，`source_code_front/dist/` 目录下会生成：
- `index.html` — 入口 HTML
- `assets/` — 打包后的 JS、CSS 文件（文件名包含哈希用于缓存控制）
- `pdf.worker.min.mjs` — PDF.js 的 worker 文件

### 注意事项

1. **API 地址配置**: 构建前务必检查 `.env.production` 中的 API 地址指向正确的后端服务器。
   - **Docker Compose + Nginx 部署**: 应设为 `http://localhost/api`（请求通过 Nginx 代理到后端）。
   - **手动部署 + 直连后端**: 保持 `http://127.0.0.1:8000/api`。
   - **前后端分离开发**: 使用 `http://localhost:8000/api`（配合后端开发服务器）。

2. **视口单位 (vw) 适配**: 项目使用 `postcss-px-to-viewport-8-plugin` 进行移动端适配，基准宽度为 `1380px`（适配 11 寸平板横屏）。如需修改，编辑 `vite.config.js` 中的 `viewportWidth`。

3. **Node 版本**: 构建环境必须满足 `package.json` 中 `engines.node` 的要求（>=20.19.0 || >=22.12.0）。

4. **构建耗时**: 首次构建较慢（需下载依赖），后续构建通常 10-30 秒完成。

---

## 环境变量说明

### 后端环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DB_HOST` | 数据库主机 | `db` |
| `DB_PORT` | 数据库端口 | `5432` |
| `DB_NAME` | 数据库名 | `postgres` |
| `DB_USER` | 数据库用户 | `postgres` |
| `DB_PASSWORD` | 数据库密码 | `postgres` |
| `REDIS_HOST` | Redis 主机 | `redis` |
| `REDIS_PORT` | Redis 端口 | `6379` |
| `REDIS_PASSWORD` | Redis 密码 | `redis123` |
| `BASE_API` | AI 接口地址（OpenAI 兼容） | `""`（需设置） |
| `API_KEY` | AI 接口密钥 | `""`（需设置） |
| `SECRET_KEY` | JWT 签名密钥 | `Default_value`（**生产环境务必修改**） |

> **安全提醒**: 生产环境部署前，请务必修改以下默认值：
> - `SECRET_KEY` — JWT 密钥
> - `POSTGRES_PASSWORD` — 数据库密码
> - `REDIS_PASSWORD` — Redis 密码

### 前端环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VITE_API_BASE_URL` | API 请求基础地址 | `http://127.0.0.1:8000/api` |
| `VITE_RESOURCE_BASE_URL` | 静态资源基础地址 | `http://127.0.0.1:8000/api` |

---

## 目录结构

```
AIEES/
├── app/                          # 后端 FastAPI 应用
│   ├── api/v1/                   # API 路由
│   │   ├── auth.py               # 认证接口
│   │   ├── course.py             # 课程接口
│   │   ├── classes.py            # 班级接口
│   │   ├── services.py           # AI 服务接口
│   │   ├── student.py            # 学生端接口
│   │   ├── organizatoin.py       # 组织接口
│   │   └── admin.py              # 管理员接口
│   ├── core/                     # 核心功能
│   │   ├── database.py           # 数据库引擎
│   │   ├── redis_pool.py         # Redis 连接池
│   │   ├── arq_jobs.py           # ARQ 异步任务
│   │   ├── security.py           # JWT/密码安全
│   │   ├── captcha.py            # 验证码
│   │   ├── rate_limiter.py       # 限流
│   │   ├── exceptions.py         # 异常处理
│   │   ├── response.py           # 统一响应
│   │   ├── tools.py              # AI 调用工具
│   │   └── formatters.py         # 格式化工具
│   ├── crud/                     # 数据库操作
│   │   └── db.py                 # 数据访问层
│   ├── model/
│   │   ├── tables/models.py      # 数据库表模型
│   │   └── schema/               # Pydantic 校验模型
│   ├── Config.py                 # 全局配置
│   ├── main.py                   # FastAPI 入口
│   └── start_worker.py           # Worker 启动
│
├── source_code_front/            # 前端 Vue 源码
│   ├── src/
│   │   ├── api/                  # API 请求封装
│   │   ├── router/               # 路由配置
│   │   ├── views/                # 页面组件
│   │   │   ├── student/          # 学生端页面
│   │   │   ├── teacher/          # 教师端页面
│   │   │   └── admin/            # 管理端页面
│   │   ├── components/           # 通用组件
│   │   ├── styles/               # 全局样式
│   │   ├── utils/                # 工具函数
│   │   ├── App.vue               # 根组件
│   │   └── main.js               # 入口文件
│   ├── public/                   # 静态资源
│   ├── index.html                # HTML 模板
│   ├── vite.config.js            # Vite 配置
│   └── package.json              # 依赖管理
│
├── frontend/dist/                # 前端构建产物（Nginx 使用）
├── static/uploads/               # 文件上传目录
│   ├── covers/                   # 封面图片
│   ├── pdfs/                     # PDF 文件
│   └── videos/                   # 视频文件
├── logs/                         # 日志文件
│   ├── nginx/                    # Nginx 日志
│   ├── ai.log                    # AI 调用日志
│   ├── system.log                # 系统日志
│   └── upstream.log              # 上游服务日志
│
├── docker-compose.yml            # Docker Compose 编排
├── Dockerfile                    # 后端镜像构建
├── nginx.conf                    # Nginx 配置
├── requirements.txt              # Python 依赖
└── README.md                     # 本文件
```

---

## 角色说明

| 角色 | 说明 | 默认账号 |
|------|------|----------|
| `student` | 学生 — 课程学习、AI 导师对话、完成测验 | 需在后台创建 |
| `teacher` | 教师 — 课程管理、学情查看、教学分析 | 需在后台创建 |
| `admin` | 管理员 — 组织管理、账号管理、系统配置 | `Admin / Default_value` |

> **首次使用**: 使用管理员账号（ID: `Admin`，密码: `Default_value`）登录后，先创建「学校组织」，然后导入教师和学生账号。

---

## 常见问题

### Q: 启动后访问页面显示空白或 502？

检查 Nginx 日志和 API 服务状态：

```bash
docker compose logs nginx
docker compose logs api
```

常见原因：API 服务尚未就绪（数据库连接超时），等待 10-20 秒后刷新。

### Q: 数据库连接失败？

确保数据库服务已启动且健康：

```bash
docker compose ps
docker compose logs db
```

### Q: 如何修改上传文件大小限制？

编辑 `app/Config.py` 中的 `Limit` 类，然后重启 API 服务：

```python
class Limit:
    MAX_VIDEO_SIZE: int = 500 * 1024 * 1024  # 500MB
    MAX_PDF_SIZE: int = 50 * 1024 * 1024     # 50MB
```

同时修改 `nginx.conf` 中的 `client_max_body_size 500M;`。

### Q: 如何备份数据库？

```bash
docker exec psql pg_dump -U postgres postgres > backup.sql
```

### Q: Worker 没有执行异步任务？

检查 Redis 连接：

```bash
docker compose logs worker
docker compose exec redis redis-cli -a redis123 ping
```

### Q: 如何更新前端代码？

```bash
cd source_code_front
git pull
npm install
npm run build
cp -r dist/* ../frontend/dist/
docker compose restart nginx
```

---

## License

MIT License
