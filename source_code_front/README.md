# AIEES 前端 — Vue 3 + Vite + Vant

GAI 科学素养平台的前端 SPA，基于 Vue 3 组合式 API + Vant UI 组件库 + Vite 8 构建，适配平板/手机端。

---

## 技术栈

- **框架**: Vue 3 (Composition API, `<script setup>`)
- **构建**: Vite 8
- **UI**: Vant 4 (移动端组件库)
- **状态管理**: Pinia
- **路由**: Vue Router 4 (History 模式)
- **图表**: ECharts 6
- **HTTP**: Axios
- **Markdown**: markdown-it + katex + turndown
- **文档预览**: PDF.js, mammoth.js (Word)
- **适配**: postcss-px-to-viewport (vw 移动端适配)

---

## 目录结构

```
source_code_front/
├── public/                     # 静态资源(不经过 Vite 处理)
│   └── pdf.worker.min.mjs      # PDF.js worker
├── src/
│   ├── api/                    # API 请求封装
│   │   ├── admin.js            # 管理员接口
│   │   ├── auth.js             # 认证接口
│   │   ├── classes.js          # 班级接口
│   │   ├── course.js           # 课程接口
│   │   ├── services.js         # AI 服务接口
│   │   ├── student.js          # 学生端接口
│   │   └── utils.js            # 请求工具 (Axios 实例)
│   ├── components/             # 通用组件
│   ├── router/
│   │   └── index.js            # 路由配置 & 守卫
│   ├── styles/
│   │   └── global.css          # 全局样式 & CSS 变量
│   ├── utils/                  # 工具函数
│   ├── views/                  # 页面组件
│   │   ├── Login.vue           # 学生/教师登录
│   │   ├── student/            # 学生端页面
│   │   │   ├── Index.vue       # 学生首页
│   │   │   ├── Resources.vue   # 课程中心
│   │   │   ├── CourseStu.vue   # 课程详情
│   │   │   ├── StudentStudy.vue# 章节学习
│   │   │   └── TaskDetail.vue  # 任务作答
│   │   ├── teacher/            # 教师端页面
│   │   │   ├── IndexTeacher.vue# 教师首页
│   │   │   ├── ResourceManage.vue# 课程管理
│   │   │   └── CourseTeacher.vue# 课程编辑
│   │   └── admin/              # 管理端页面
│   │       ├── AdminLogin.vue  # 管理员登录
│   │       └── AdminManagement.vue# 系统管理
│   ├── App.vue                 # 根组件
│   └── main.js                 # 入口文件
├── .env.development            # 开发环境变量
├── .env.production             # 生产环境变量
├── index.html                  # HTML 模板
├── vite.config.js              # Vite 配置
├── jsconfig.json               # JS 配置
├── package.json                # 依赖 & 脚本
└── README.md                   # 本文件
```

---

## 路由结构

| 路径 | 页面 | 角色 |
|------|------|------|
| `/` | 学生/教师登录 | 公开 |
| `/admin/login` | 管理员登录 | 公开 |
| `/index` | 学生首页 | student |
| `/resources` | 课程中心 | student |
| `/course/:courseId` | 课程详情 | student |
| `/course/study` | 学习页面 | student |
| `/course/task` | 任务作答 | student |
| `/teacher/index` | 教师首页 | teacher |
| `/teacher/resources` | 课程管理 | teacher |
| `/teacher/course/:course_id` | 课程编辑 | teacher |
| `/admin/manage` | 系统管理 | admin |

路由守卫根据 `localStorage` 中的 `token` 和 `role` 进行权限控制。

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VITE_API_BASE_URL` | API 请求基地址 | `http://127.0.0.1:8000/api` |
| `VITE_RESOURCE_BASE_URL` | 静态资源基地址 | `http://127.0.0.1:8000/api` |

生产环境修改 `.env.production`，开发环境修改 `.env.development`。

---

## 可用脚本

```bash
# 启动开发服务器（热重载）
npm run dev

# 构建生产版本
npm run build

# 预览构建产物
npm run preview
```

---

## 开发指南

### 启动开发环境

```bash
# 1. 安装依赖
npm install

# 2. 确保后端运行在 localhost:8000

# 3. 启动开发服务器 (默认 :5173)
npm run dev
```

### 构建生产版本

```bash
npm run build
# 产物在 dist/ 目录
```

---

## 适配说明

项目使用 `postcss-px-to-viewport-8-plugin` 进行移动端 vw 适配：

- **设计稿基准宽度**: 1380px (11 寸平板横屏)
- **转换单位**: px → vw
- **白名单类名**: `.ignore-scale` (加入此类的元素不缩放)

如需调整，编辑 `vite.config.js` 中的 `viewportWidth`。
