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
- [开发更新指南](#开发更新指南)
  - [更新后端代码（Python）](#更新后端代码python)
  - [更新前端代码（Vue）](#更新前端代码vue)
- [环境变量说明](#环境变量说明)
- [目录结构](#目录结构)
- [角色说明](#角色说明)
- [常见问题](#常见问题)

---

## 系统架构

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│              │      │              │      │              │
│  浏览器/客户端│─────▶│   Nginx       │─────▶│  FastAPI     │
│  (Vue SPA)   │      │  (反向代理 +   │      │  (API 服务)   │
│              │◀─────│   静态文件)    │◀─────│              │
└──────────────┘      └──────────────┘      └──────┬──┬─────┘
                                                     │  │
                    ┌────────────────────────────────┘  └──────────────┐
                    │                                                   │
                    ▼                                                   ▼
            ┌──────────────┐                                  ┌──────────────┐
            │  PostgreSQL  │                                  │    Redis      │
            │  (主数据库)   │                                  │  (缓存/队列)   │
            └──┬───┬───┬───┘                                  └──────┬───────┘
               │   │   │                                              │
               │   │   └──────────────────────────────┐               │
               │   │                                  │               │
               │   ▼                                  ▼               ▼
               │  ┌──────────────────────────────────────────────────────┐
               │  │                     Taskiq                          │
               │  │  ┌────────────────────┐       ┌──────────────────┐  │
               └──│──│  Worker             │       │  Scheduler       │  │
                  │  │  (异步任务, AI 评分)  │       │  (定时任务调度)   │  │
                  │  └────────────────────┘       └──────────────────┘  │
                  └──────────────────────────────────────────────────────┘
```


## 技术栈

### 后端 (app/)
- **框架**: Python 3.14, FastAPI, Uvicorn/Gunicorn
- **ORM**: SQLModel + SQLAlchemy + asyncpg
- **数据库**: PostgreSQL 18
- **缓存/队列**: Redis 8 + Taskiq
- **AI 集成**: OpenAI API (兼容接口)
- **认证**: JWT (PyJWT), Argon2 密码哈希
- **文件处理**: Pillow, python-multipart, aiofiles
- **包管理**: uv + pyproject.toml
- **代码检查**: Ruff, mypy

### 前端 (source_code_front/)
- **框架**: Vue 3 (Composition API, `<script setup>`)
- **构建工具**: Vite 8
- **UI 组件库**: Vant 4 (移动端优先)
- **状态管理**: Pinia 3
- **路由**: Vue Router 4
- **图表**: ECharts 6
- **HTTP**: Axios
- **Markdown**: markdown-it, markdown-it-texmath, katex, turndown
- **代码高亮**: PrismJS
- **文档预览**: PDF.js, mammoth (Word)
- **安全过滤**: DOMPurify
- **时间处理**: dayjs
- **表格处理**: xlsx
- **语音录制**: @breezystack/lamejs (PCM → MP3), @microsoft/fetch-event-source (SSE)
- **工具库**: @vueuse/core
- **移动端适配**: postcss-px-to-viewport-8-plugin

---

## 环境要求

| 依赖 | 版本要求 |
|------|----------|
| Docker | >= 24.0 |
| Docker Compose | >= 2.20 (V2) |
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
cd ..
```

> `npm run build` 会自动创建 `frontend/dist/` 目录并将构建产物输出其中。
> 如需自定义后端地址，构建前编辑 `source_code_front/.env.production` 中的 `VITE_API_BASE_URL`。

### 3. 配置环境变量

编辑项目根目录的 `.env` 文件，所有环境变量已在此统一管理。Docker Compose 会自动读取该文件并注入到对应容器中。

**必须配置的项：**
- `ADMIN_NAME` — 管理员账号名
- `ADMIN_PASSWORD` — 管理员密码
- `SECRET_KEY` — JWT 签名密钥（生产环境务必修改）
- `AI_BASE_URL` — AI 接口地址（OpenAI 兼容）
- `AI_API_KEY` — AI 接口密钥
- `AI_MODEL_TEXT` — 文本模型名称
- `AI_MODEL_ASR` — 语音识别模型名称

**其他默认值已可用，如需修改：**
- `POSTGRES_PASSWORD` — 数据库密码
- `REDIS_PASSWORD` — Redis 密码

### 4. 启动所有服务

```bash
docker compose up -d
```

首次启动会构建后端镜像，耗时约 5-10 分钟。

### 5. 初始化数据库

首次部署或数据库表结构变更后，需手动执行建表和初始数据写入：

```bash
# 进入 API 容器执行
docker compose exec api python -m app.infra.scripts.init_db
```

执行成功会显示：
```
✓ 数据表创建完成
✓ 初始数据写入完成
```

> **说明**：该脚本使用 `CREATE TABLE IF NOT EXISTS`，可安全重复执行，不会覆盖已有数据。

### 6. 验证部署

- **前端页面**: http://localhost
- **后端 API**: http://localhost/api/ （通过 Nginx 代理）
- **Swagger 文档**: 默认不对外暴露，如需访问，在 `docker-compose.yml` 的 `api` 服务中添加 `ports: - "8000:8000"`，然后访问 `http://localhost:8000/docs`

> ⚠️ **首次登录**：执行初始化脚本后，系统会自动创建管理员账号，账号信息在 `.env` 文件中配置：
> - **账号**: `ADMIN_NAME` 的值（默认 `Admin`）
> - **密码**: `ADMIN_PASSWORD` 的值
>
> **配置方法**：编辑项目根目录的 `.env` 文件，修改以下两项：
> ```env
> ADMIN_NAME=你的管理员账号
> ADMIN_PASSWORD=你的管理员密码
> ```
> 修改后需重新执行初始化脚本：`docker compose exec api python -m app.infra.scripts.init_db`

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

## 开发更新指南

### 更新后端代码（Python）

当你修改了 `app/` 目录下的 Python 代码后，需要重新构建 `api` 和 `worker` 镜像并重启容器：

```bash
# 重新构建并重启 api 和 worker 服务
docker compose up -d --build api worker
```

> **说明**：
> - `--build` 会强制重新构建镜像，确保最新代码被打包
> - 如果只修改了业务逻辑，也可使用 `docker compose restart api worker` 快速重启（但不会重新构建镜像）
> - 如果修改了 `pyproject.toml` 或 `uv.lock`，必须使用 `--build` 重新构建

### 更新前端代码（Vue）

当你修改了 `source_code_front/` 目录下的前端代码后，重新构建后重启 Nginx 即可生效：

```bash
cd source_code_front
npm run build
cd ..
docker compose restart nginx
```

> `npm run build` 直接输出到 `frontend/dist/`（通过 `vite.config.js` 中的 `build.outDir` 配置），无需手动复制。
> Nginx 容器通过 volume 挂载 `./frontend/dist` 目录，替换文件后只需 `restart` 即可生效。

---

## 环境变量说明

### 后端环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ADMIN_NAME` | 管理员账号名 | `Admin` |
| `ADMIN_PASSWORD` | 管理员密码 | 需设置 |
| `DB_HOST` | 数据库主机 | `db` |
| `DB_PORT` | 数据库端口 | `5432` |
| `DB_NAME` | 数据库名 | `postgres` |
| `DB_USER` | 数据库用户 | `postgres` |
| `DB_PASSWORD` | 数据库密码 | 需设置 |
| `REDIS_HOST` | Redis 主机 | `redis` |
| `REDIS_PORT` | Redis 端口 | `6379` |
| `REDIS_PASSWORD` | Redis 密码 | 需设置 |
| `AI_BASE_URL` | AI 接口地址（OpenAI 兼容） | 需设置 |
| `AI_API_KEY` | AI 接口密钥 | 需设置 |
| `AI_MODEL_TEXT` | 文本模型名称 | 需设置 |
| `AI_MODEL_ASR` | 语音识别模型名称 | 需设置 |
| `SECRET_KEY` | JWT 签名密钥 | 需设置 |
| `CORS_ORIGINS` | CORS 允许来源（逗号分隔） | `http://localhost:5173,http://127.0.0.1:5173` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `SLOW_QUERY_MS` | SQL 慢查询阈值（毫秒） | `500` |
| `COMPOSE_PROJECT_NAME` | Docker Compose 项目名 | `aiees` |
| `VERSION` | 版本标签 | `1.0.0` |

### 前端环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VITE_API_BASE_URL` | API 请求基础地址 | `/api`（开发）/ `http://localhost/api`（生产） |
| `VITE_RESOURCE_BASE_URL` | 静态资源基础地址 | `/api`（开发）/ `http://localhost/api`（生产） |

> **安全提醒**: 生产环境部署前，请务必修改以下默认值：
> - `ADMIN_NAME` / `ADMIN_PASSWORD` — 管理员账号密码
> - `SECRET_KEY` — JWT 密钥
> - `DB_PASSWORD` / `POSTGRES_PASSWORD` — 数据库密码
> - `REDIS_PASSWORD` — Redis 密码
> - `AI_API_KEY` — AI 接口密钥

---

## 目录结构

```
AIEES/
├── app/                          # 后端 FastAPI 应用
│   ├── api/                      # API 路由
│   │   ├── dependencies.py       # 公共依赖项（角色验证等）
│   │   └── v1/
│   │       ├── admin.py          # 管理员接口
│   │       ├── auth.py           # 认证接口
│   │       ├── classes.py        # 班级接口
│   │       ├── course.py         # 课程接口
│   │       ├── organization.py   # 组织接口
│   │       ├── service.py        # AI 服务接口
│   │       └── student.py        # 学生端接口
│   ├── common/                   # 公共工具
│   │   ├── formatters.py         # 格式化工具
│   │   ├── pagination.py         # 分页工具
│   │   ├── response.py           # 统一响应
│   │   └── tools.py              # AI 调用工具
│   ├── core/                     # 核心功能
│   │   ├── ai_client.py          # AI 客户端
│   │   ├── config.py             # 全局配置
│   │   ├── database.py           # 数据库引擎
│   │   ├── exceptions.py         # 异常处理
│   │   ├── logging.py            # 日志配置
│   │   ├── middleware.py         # 中间件
│   │   ├── prompts.py            # AI 提示词
│   │   ├── rate_limiter.py       # 限流
│   │   ├── redis.py              # Redis 连接池
│   │   └── security.py           # JWT/密码安全
│   ├── infra/                    # 基础设施层
│   │   ├── alembic/              # 数据库迁移预留
│   │   └── scripts/              # 运维脚本
│   │       ├── init_db.py        # 建表 + 初始数据
│   │       └── init_data.py      # 管理员数据生成
│   ├── model/
│   │   └── models.py             # 数据库表模型
│   ├── schema/                   # Pydantic 校验模型
│   │   ├── admin.py
│   │   ├── chapter.py
│   │   ├── chat.py
│   │   ├── class_.py
│   │   ├── common.py
│   │   ├── course.py
│   │   ├── enums.py
│   │   ├── gai_task.py
│   │   ├── organization.py
│   │   ├── task.py
│   │   └── user.py
│   ├── service/                  # 业务逻辑层
│   │   ├── analysis_service.py   # 学情分析
│   │   ├── auth_service.py       # 认证服务
│   │   ├── class_service.py      # 班级服务
│   │   ├── course_service.py     # 课程服务
│   │   ├── organization_service.py # 组织服务
│   │   ├── student_service.py    # 学生服务
│   │   ├── task_service.py       # 任务服务
│   │   └── user_service.py       # 用户服务
│   ├── task/                     # Taskiq 任务队列
│   │   ├── broker.py             # 任务 Broker
│   │   ├── scheduler.py          # 定时调度器
│   │   └── job/                  # 任务实现
│   │       ├── course_analysis.py
│   │       └── grading.py
│   ├── util/                     # 工具函数
│   │   ├── captcha_util.py       # 验证码
│   │   └── time_util.py          # 时间工具
│   ├── test/                     # 测试与本地开发指南
│   │   └── README.md             # 本地开发环境搭建说明
│   └── main.py                   # FastAPI 入口
│
├── source_code_front/            # 前端 Vue 源码
│   ├── src/
│   │   ├── api/                  # API 请求封装
│   │   │   ├── admin.js
│   │   │   ├── classes.js
│   │   │   ├── course.js
│   │   │   ├── service.js        # SSE 流式聊天/语音识别
│   │   │   ├── student.js
│   │   │   └── utils.js
│   │   ├── router/               # 路由配置（含路由守卫）
│   │   ├── views/                # 页面组件
│   │   │   ├── Login.vue         # 学生/教师登录页
│   │   │   ├── student/          # 学生端页面（5 个）
│   │   │   ├── teacher/          # 教师端页面（3 个）
│   │   │   └── admin/            # 管理端页面（含独立登录）
│   │   ├── components/           # 通用组件
│   │   │   ├── AppHeader.vue     # 顶部导航栏
│   │   │   └── GAI.vue           # GAI 对话助手（含语音输入）
│   │   ├── styles/               # 全局样式（组件级 CSS）
│   │   │   ├── global.css
│   │   │   ├── components/
│   │   │   └── views/
│   │   ├── utils/                # 工具函数
│   │   │   ├── request.js        # Axios 实例（拦截器）
│   │   │   ├── sseRequest.js     # SSE 流式请求封装
│   │   │   └── mp3EncodeWorker.js # Web Worker 音频编码
│   │   ├── App.vue               # 根组件
│   │   └── main.js               # 入口文件
│   ├── public/                   # 静态资源
│   ├── index.html                # HTML 模板
│   ├── vite.config.js            # Vite 配置
│   └── package.json              # 依赖管理
│
├── frontend/dist/                # 前端构建产物（npm run build 自动生成，Nginx 使用）
├── static/uploads/               # 文件上传目录
│   ├── covers/                   # 封面图片
│   ├── pdfs/                     # PDF 文件
│   └── videos/                   # 视频文件
│
├── fastapi/                      # 后端 Docker 构建
│   └── Dockerfile                # 后端镜像构建（基于 uv，多阶段）
├── nginx/                        # Nginx 配置目录
│   ├── nginx.conf                # 生产 Nginx 配置
│   └── nginx.dev.conf            # 开发 Nginx 配置（本地开发模式使用）
│
├── .env                          # 环境变量配置（会注入 Docker 容器）
├── .env.example                  # 环境变量模板
├── .dockerignore                 # Docker 构建忽略规则
├── docker-compose.yml            # 生产 Docker Compose 编排
├── docker-compose.dev.yml        # 本地开发 Docker Compose 编排
├── pyproject.toml                # Python 依赖与项目配置（Docker 构建使用）
├── uv.lock                       # 依赖锁定文件
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

编辑 `app/core/config.py` 中的 `Limit` 类，然后重启 API 服务：

```python
class Limit:
    MAX_VIDEO_SIZE: int = 500 * 1024 * 1024  # 500MB
    MAX_PDF_SIZE: int = 50 * 1024 * 1024     # 50MB
```

同时修改 `nginx/nginx.conf` 中的 `client_max_body_size 500M;`（本地开发为 `nginx/nginx.dev.conf`，修改后需重启 nginx / nginx-dev 容器）。

### Q: 如何备份数据库？

```bash
docker compose exec db pg_dump -U postgres postgres > backup.sql
```

### Q: Worker 没有执行异步任务？

检查 Redis 连接：

```bash
docker compose logs worker
docker compose exec redis redis-cli -a your-redis-password ping
```

### Q: 如何更新前端代码？

```bash
cd source_code_front
git pull
npm install
npm run build
cd ..
docker compose restart nginx
```

---

## License

MIT License
