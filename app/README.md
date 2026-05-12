# AIEES 后端 — FastAPI + PostgreSQL + Redis

基于 FastAPI 的异步 Python 后端，为 GAI 科学素养平台提供 RESTful API、AI 对话、自动评分和学情分析能力。

---

## 技术栈

- **框架**: Python 3.14, FastAPI, Uvicorn / Gunicorn
- **ORM**: SQLModel + SQLAlchemy 2.0 (async) + asyncpg
- **数据库**: PostgreSQL 18
- **缓存/队列**: Redis 8 + ARQ (异步任务队列)
- **AI**: OpenAI SDK (兼容 GLM 等第三方 API)
- **认证**: JWT (PyJWT)
- **文件**: aiofiles, Pillow

---

## 目录结构

```
app/
├── api/v1/                     # API 路由层
│   ├── auth.py                 # 登录、验证码、修改密码
│   ├── course.py               # 课程 CRUD
│   ├── classes.py              # 班级管理
│   ├── services.py             # AI 对话(SSE流式)、文件上传
│   ├── student.py              # 学生端接口
│   ├── organizatoin.py         # 学校组织管理
│   └── admin.py                # 管理员后台接口
├── core/                       # 核心基础设施
│   ├── database.py             # SQLAlchemy 异步引擎 & 会话工厂
│   ├── redis_pool.py           # Redis 连接池 (缓存 + ARQ)
│   ├── arq_jobs.py             # ARQ Worker 定义 (AI评分/学情分析)
│   ├── security.py             # JWT 签发/验证 & 密码哈希
│   ├── captcha.py              # 数学验证码生成
│   ├── rate_limiter.py         # 登录限流/锁定
│   ├── exceptions.py           # 全局异常拦截器
│   ├── response.py             # 统一响应格式
│   ├── tools.py                # AI 客户端、文件上传工具
│   └── formatters.py           # 数据格式化工具
├── crud/
│   └── db.py                   # 数据访问层 (所有数据库操作)
├── model/
│   ├── tables/models.py        # SQLModel 表定义
│   └── schema/                 # Pydantic 请求/响应模型
│       ├── schema.py           # 通用模型 (用户、Token等)
│       ├── course.py           # 课程相关模型
│       └── classes.py          # 班级相关模型
├── Config.py                   # 全局配置 (URL、CORS、Prompt等)
├── main.py                     # FastAPI 应用入口 & 生命周期
└── start_worker.py             # Worker 启动入口
```

---

## 核心 API 分组

| 前缀 | 说明 |
|------|------|
| `/api/auth` | 登录、验证码、密码修改 |
| `/api/course` | 课程管理 (CRUD、章节、任务) |
| `/api/classes` | 班级管理 |
| `/api/student` | 学生端 (学习进度、AI导师对话) |
| `/api/services` | AI 对话 (SSE 流式)、文件上传 |
| `/api/organization` | 学校组织管理 |
| `/api/admin` | 系统管理后台 |

---

## 异步任务 (ARQ Worker)

系统使用 ARQ 处理以下后台任务：

| 任务 | 触发器 | 说明 |
|------|--------|------|
| `process_task_grading_job` | 提交测验后触发 | AI 自动评分 + 错题分析 |
| `process_single_course_analysis_job` | 每日定时 (03:00) | 课程级综合学情分析 |
| `daily_update_all_courses_analysis_job` | 每日定时 (03:00) | 遍历所有课程触发分析 |

Worker 启动命令：`arq app.core.arq_jobs.WorkerSettings`

---

## AI 功能说明

后端通过 OpenAI 兼容接口调用大模型，支持以下 AI 能力：

1. **苏格拉底式 AI 导师** — 学生端对话，只引导不给答案
2. **主观题自动评分** — 任务测验的主观题 AI 批改
3. **学情分析报告** — 学生个人 & 课程整体分析
4. **教学策略建议** — 教师端数据分析支持

> **模型**: 默认使用 `GLM-5.1`（兼容 OpenAI SDK 的任意模型均可）
> **配置**: 通过环境变量 `BASE_API`（接口地址）和 `API_KEY`（密钥）配置。代码已从 `Config.py` → `tools.py` 自动读取（参见 `app/Config.py:42-43` 和 `app/core/tools.py:26-30`）。

---

## 安全机制

- **JWT 令牌认证** — 24 小时过期
- **登录安全策略** — 3 次失败弹出验证码，10 次失败锁定 15 分钟
- **CORS 白名单** — 仅允许配置的域名访问
- **文件类型白名单** — 上传文件严格校验 MIME 和后缀
- **密码哈希** — 使用 `pwdlib` (argon2)

---

## 依赖

参见项目根目录 [requirements.txt](../requirements.txt)
