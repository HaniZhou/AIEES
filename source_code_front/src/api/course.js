// src/api/course.js
import request from "@/utils/request.js";

/**
 * @description 创建新课程（包含封面上传与教案解析）
 * @method POST /course/create
 * @requestParams { File } cover - 课程封面纯文件对象
 * @requestParams { string } course_name - 课程名称
 * @requestParams { string } selected_classes - 选中的班级 JSON 字符串
 * @requestParams { string } teaching_plan - 由 Word 解析出的 Markdown 文本
 * @response { code: number, data: { course_id: string } }
 * @interactionNotes 使用 FormData 传参，axios 会自动设置含有 boundary 的请求头。禁止手动设置 Content-Type。
 */
export function create_new_course(cover, course_name, selectedClasses, wordMarkdown) {
    const formData = new FormData();
    if (cover) {
        formData.append("cover", cover);
    }
    formData.append("course_name", course_name);
    formData.append("selected_classes", selectedClasses);
    formData.append("teaching_plan", wordMarkdown);
    return request.post("/course/create", formData);
}

/**
 * @description 获取教师课程列表（分页）
 * @method GET /course/get/teacher
 * @requestParams { number } page - 页码，默认 1
 * @response { code: number, data: { courses: Array<{ course_id: string, course_name: string, course_cover: string }> } }
 * @interactionNotes 后端保证返回标准信封。业务层直接解构 res.data.courses 使用，禁止写兜底逻辑。
 */
export function get_teacher_courses(page = 1, signal) {
    return request.get("/course/get/teacher", {params: {page}, signal});
}

/**
 * @description 获取课程详细信息（教师端）
 * @method GET /course/:courseId
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @response { code: number, data: { course_id: string, course_name: string, course_cover: string, teaching_plan: string, invited_code: string, is_invitation_valid: boolean } }
 * @interactionNotes 后端返回标准信封。直接解构 res.data 获取详情。
 */
export function get_course_detail(courseId) {
    return request.get(`/course/${courseId}`);
}

/**
 * @description 删除课程及其所有关联数据
 * @method DELETE /course/:courseId
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @response { code: number, data: {} }
 */
export function delete_course(courseId) {
    return request.delete(`/course/${courseId}`);
}

/**
 * @description 上传课程资源文件（视频/PDF）
 * @method POST /service/resource
 * @requestParams { File } file - 资源文件对象
 * @response { code: number, data: { path: string } }
 * @interactionNotes [重要] 后端路由已修正为 /service/resource。返回标准信封，业务层直接使用 res.data.path。
 */
export function upload_resource(file) {
    const formData = new FormData();
    formData.append("file", file);
    return request.post("/service/resource", formData);
}

/**
 * @description 创建测验任务
 * @method POST /course/:courseId/tasks
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { object } payload - 需包含 task_title, quiz, answer, deadline
 * @response { code: number, data: { task_id: string } }
 * @interactionNotes [红线] deadline 必须传 ISO 8601 UTC 格式字符串（如 "2025-01-15T15:59:59Z"），严禁拼接 +08:00 等本地时区偏移。
 */
export function create_task(courseId, payload) {
    return request.post(`/course/${courseId}/tasks`, payload);
}

/**
 * @description 更新测验任务
 * @method PUT /course/:courseId/tasks/:taskId
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } taskId - 路由参数，任务 ID
 * @requestParams { object } payload - 需包含 task_title, quiz, answer, deadline
 * @response { code: number, data: { task_id: string } }
 * @interactionNotes [红线] deadline 必须传 "YYYY-MM-DDTHH:mm:ssZ" 格式。
 */
export function update_task(courseId, taskId, payload) {
    return request.put(`/course/${courseId}/tasks/${taskId}`, payload);
}

/**
 * @description 删除测验任务
 * @method DELETE /course/:courseId/tasks/:taskId
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } taskId - 路由参数，任务 ID
 * @response { code: number, data: {} }
 */
export function delete_task(courseId, taskId) {
    return request.delete(`/course/${courseId}/tasks/${taskId}`);
}

/**
 * @description 创建 GAI 任务
 * @method POST /course/:courseId/gai-tasks
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { object } payload - 需包含 analysis_task_title, task_description, analysis_description, evaluation_criterion, deadline(可选)
 * @response { code: number, data: { analysis_task_id: string } }
 * @interactionNotes [红线] deadline 必须传 "YYYY-MM-DDTHH:mm:ssZ" 格式。
 */
export function create_gai_task(courseId, payload) {
    return request.post(`/course/${courseId}/gai-tasks`, payload);
}

/**
 * @description 更新 GAI 任务
 * @method PUT /course/:courseId/gai-tasks/:taskId
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } taskId - 路由参数，任务 ID
 * @requestParams { object } payload - 需包含 analysis_task_title, task_description 等, deadline(可选)
 * @response { code: number, data: { analysis_task_id: string } }
 * @interactionNotes [红线] deadline 必须传 "YYYY-MM-DDTHH:mm:ssZ" 格式。
 */
export function update_gai_task(courseId, taskId, payload) {
    return request.put(`/course/${courseId}/gai-tasks/${taskId}`, payload);
}

/**
 * @description 删除 GAI 任务
 * @method DELETE /course/:courseId/gai-tasks/:taskId
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } taskId - 路由参数，任务 ID
 * @response { code: number, data: {} }
 */
export function delete_gai_task(courseId, taskId) {
    return request.delete(`/course/${courseId}/gai-tasks/${taskId}`);
}

/**
 * @description 局部更新课程信息（如修改邀请码状态、课程名称等）
 * @method PATCH /course/:courseId
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { object } payload - 仅允许包含：course_name (string), is_invitation_valid (boolean)
 * @response { code: number, data: { course_id: string, course_name: string, is_invitation_valid: boolean } }
 * @interactionNotes [红线] 后端 Pydantic 模型无 invited_code 字段。严禁在 payload 中传入 invited_code，否则后端会直接忽略。
 */
export function update_course(courseId, payload) {
    return request.patch(`/course/${courseId}`, payload);
}

/**
 * @description 获取任务详情（含题目及答案）- 教师端编辑使用
 * @method GET /course/:courseId/tasks/:taskId/edit
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } taskId - 路由参数，任务 ID
 * @response { code: number, data: { task_title: string, deadline: string, quiz: Array<{ type: string, title: string, options: Array<string> }>, answer: Array<{ type: string, correct_index: Array<number> }> } }
 * @interactionNotes 教师端编辑专用，返回包含正确答案的完整题目信息，格式与 update_task 的 payload 对应。
 */
export function get_task_detail_for_edit(courseId, taskId) {
    return request.get(`/course/${courseId}/tasks/${taskId}/edit`);
}


/**
 * @description 获取子任务或测验任务的完成详情
 * @method GET /course/:courseId/completion-details
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } type - 类型：'section' 或 'task'
 * @requestParams { number } targetId - 目标 ID
 * @response { code: number, data: { student_records: Array<{ student_id: string, student_name: string, is_completed: boolean, score: number }> } }
 */
export function get_completion_details(courseId, type, targetId) {
    return request.get(`/course/${courseId}/completion-details`, {
        params: {type, target_id: targetId}
    });
}

/**
 * @description 获取某个学生对某个GAI任务的对话记录及分析
 * @method GET /course/:courseId/gai-tasks/:taskId/student-analysis
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } taskId - 路由参数，任务 ID
 * @requestParams { string } studentId - 查询参数，学生 ID
 * @response { code: number, data: { chat_history: Array<{ role: string, content: string }>, analysis_text: string } }
 */
export function get_gai_student_analysis(courseId, taskId, studentId) {
    return request.get(`/course/${courseId}/gai-tasks/${taskId}/student-analysis`, {
        params: {student_id: studentId}
    });
}

/**
 * @description 一次性拉取课程下所有学生的原始完成记录
 * @method GET /course/:courseId/analysis/raw-records
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @response { code: number, data: { records: Array<{ student_id: string, done_section_ids: string[], done_task_ids: string[], task_scores: object }> } }
 */
export function get_analysis_raw_records(courseId) {
    return request.get(`/course/${courseId}/analysis/raw-records`);
}

/**
 * @description 按需获取 AI 分析文本
 * @method GET /course/:courseId/analysis/ai-text
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } studentId - 查询参数，学生 ID，默认 'all'
 * @response { code: number, data: { description: string } }
 */
export function get_analysis_ai_text_for_student_study(courseId, studentId = 'all') {
    return request.get(`/course/${courseId}/analysis/ai-text`, {
        params: {student_id: studentId}
    });
}

/**
 * @description 获取课程的任务列表
 * @method GET /course/:courseId/tasks
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @response { code: number, data: { tasks: Array<{ task_id: string, task_title: string, deadline: string ,is_completed:boolean}> } }
 * @interactionNotes deadline 为 "YYYY-MM-DDTHH:mm:ssZ" 格式。
 */
export function get_tasks(courseId) {
    return request.get(`/course/${courseId}/tasks`);
}

/**
 * @description 获取课程的 GAI 任务列表
 * @method GET /course/:courseId/gai-tasks
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @response { code: number, data: { gai_tasks: Array<{ analysis_task_id: string, analysis_task_title: string, task_description: string, deadline: string }> } }
 * @interactionNotes deadline 为 "YYYY-MM-DDTHH:mm:ssZ" 格式。
 */
export function get_gai_tasks(courseId) {
    return request.get(`/course/${courseId}/gai-tasks`);
}

/**
 * @description 学生获取已加入的课程列表（分页）
 * @method GET /course/student
 * @requestParams { number } page - 页码，默认 1
 * @response { code: number, data: { courses: Array<{ course_id: string, course_name: string, course_cover: string, teacher_name: string }> } }
 * @interactionNotes 后端根据 JWT 获取学生 ID，单页默认 16 条。
 */
export function get_student_courses(page = 1, signal) {
    return request.get('/course/student', {params: {page}, signal});
}

/**
 * @description 学生通过邀请码加入班级
 * @method POST /course/join
 * @requestParams { object } payload - 需包含 invite_code (string)
 * @response { code: number, data: {} }
 */
export function join_class(inviteCode) {
    return request.post('/course/join', {invite_code: inviteCode});
}

/**
 * @description 获取特定 GAI 任务下的学生列表及完成状态
 * @method GET /course/:courseId/gai-tasks/:taskId/students
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } taskId - 路由参数，任务 ID
 * @response { code: number, data: { students: Array<{ id: string, name: string, is_completed: boolean }> } }
 * @interactionNotes [重要修正] 后端返回的是 id 和 name，不再是 student_id 和 student_name。直接解构 res.data.students。
 */
export function get_gai_task_students(courseId, taskId) {
    return request.get(`/course/${courseId}/gai-tasks/${taskId}/students`);
}

/**
 * @description 获取课程下的学生列表（用于学习分析等场景）
 * @method GET /course/:courseId/students
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @response { code: number, data: { students: Array<{ id: string, name: string }> } }
 */
export function get_course_students(courseId) {
    return request.get(`/course/${courseId}/students`);
}

/**
 * @description 标记小节学习完成（学生端使用JWT）
 * @method POST /course/:courseId/sections/:sectionId/complete
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } sectionId - 路由参数，小节 ID
 * @response { code: number, data: {} }
 * @interactionNotes 成功后前端自定义 Toast 提示，禁止读 res.message。
 */
export function complete_section(courseId, sectionId) {
    return request.post(`/course/${courseId}/sections/${sectionId}/complete`);
}

/**
 * @description 提交学习难度反馈（学生端使用JWT）
 * @method POST /course/:courseId/sections/:sectionId/feedback
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } sectionId - 路由参数，小节 ID
 * @requestParams { number } difficulty - 难度值，范围 1-5
 * @response { code: number, data: {} }
 */
export function submit_feedback(courseId, sectionId, difficulty) {
    return request.post(`/course/${courseId}/sections/${sectionId}/feedback`, {
        difficulty: difficulty
    });
}

/**
 * @description 获取任务详情（含题目）- 学生端使用JWT
 * @method GET /course/:courseId/tasks/:taskId
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } taskId - 路由参数，任务 ID
 * @response { code: number, data: { task_title: string, deadline: string, questions: Array<{ question_id: string, type: string, title: string, options: Array<{ option_id: string, content: string }> }> } }
 * @interactionNotes deadline 为 "YYYY-MM-DDTHH:mm:ssZ" 格式。
 */
export function get_task_detail(courseId, taskId) {
    return request.get(`/course/${courseId}/tasks/${taskId}`);
}

/**
 * @description 提交任务答案 - 学生端使用JWT
 * @method POST /course/:courseId/tasks/:taskId/submit
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } taskId - 路由参数，任务 ID
 * @requestParams { Array } answers - 答案数组
 * @response { code: number, data: { task_score: number } }
 * @interactionNotes  后端需要时间修改和评分，不会立即返回任何评分。
 */
export function submit_task_answers(courseId, taskId, answers) {
    return request.post(`/course/${courseId}/tasks/${taskId}/submit`, {
        answers: answers
    });
}

/**
 * @description 发起 GAI 对话（异步任务）
 * @method POST /service/gai_chat
 * @requestParams { string } courseId - 课程 ID
 * @requestParams { string } taskId - 任务 ID
 * @requestParams { Array } messages - 完整对话上下文
 * @response { code: number, data: { task_id: string, status: 'processing' } }
 * @interactionNotes [P0级重大修改] 后端禁止同步阻塞等待 LLM。调用后立即返回 200 及 task_id。前端需拿着 task_id 调用 poll_gai_chat_task 轮询结果，并切换 UI 为"后台处理中"状态。
 */
export function gai_chat(courseId, taskId, messages) {
    return request.post(`/service/gai_chat`, {messages});
}

/**
 * @description 轮询 GAI 任务结果
 * @method GET /service/gai_chat/:taskId
 * @requestParams { string } taskId - 由 gai_chat 接口返回的异步任务 ID
 * @response { code: number, data: { task_id: string, status: 'processing' | 'completed' | 'failed', result?: { reply: { content: string } } } }
 * @interactionNotes 前端应设置定时器（如 2秒）轮询此接口。当 status === 'completed' 时，从 data.result.reply.content 取出最终 AI 回复；当 status === 'failed' 时停止轮询。
 */
export function poll_gai_chat_task(taskId) {
    return request.get(`/service/gai_chat/${taskId}`);
}

/**
 * @description 提交 GAI 探究任务 - 学生端使用JWT
 * @method POST /course/:courseId/gai-tasks/:taskId/submit
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } taskId - 路由参数，任务 ID
 * @requestParams { Array } messages - 对话上下文
 * @response { code: number, data: {} }
 */
export function submit_gai_task(courseId, taskId, messages) {
    return request.post(`/course/${courseId}/gai-tasks/${taskId}/submit`, {
        messages: messages
    });
}


/**
 * @description 获取学生待办学习任务列表（学生端使用JWT）
 * @method GET /student/tasks-todo
 * @response { code: number, data: { tasks: Array<{ task_id: string, task_title: string, course_name: string, course_id: string, is_completed: boolean, deadline: string }>, gai_tasks: Array<{ task_id: string, task_title: string, course_name: string, course_id: string, is_completed: boolean, deadline: string }> } }
 * @interactionNotes [重要修正] 后端严格遵循信封结构。直接解构 res.data.tasks 和 res.data.gai_tasks 使用，禁止写裸数组兼容逻辑。deadline 格式为 "YYYY-MM-DDTHH:mm:ssZ" (ISO 8601)。
 */
export function get_student_tasks_todo() {
    return request.get(`/student/tasks-todo`);
}

/**
 * @description 获取学生已提交任务的批改回顾详情
 * @method GET /course/:courseId/tasks/:taskId/review
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } taskId - 路由参数，任务 ID
 * @response { code: number, data: { task_score: number, ai_analysis: string, questions: Array<{ question_id: string, student_answer: string | Array<string>, correct_answer: string | Array<string> }> } }
 * @interactionNotes 仅在 is_completed === true 时调用。后端保证 questions 数组顺序与详情接口完全一致，且不返回 null。
 */
export function get_task_review(courseId, taskId) {
    return request.get(`/course/${courseId}/tasks/${taskId}/review`);
}

/**
 * @description 上报学生增量学习时长（秒）
 * @method POST /course/:courseId/study-duration
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { number } duration - 本次学习的秒数（正整数）
 * @response { code: number, data: {} }
 * @interactionNotes 前端分片多次上报（切后台、离开页面时触发），后端负责累加该学生该课程的周时长。
 */
export function report_study_duration(courseId, duration) {
    return request.post(`/course/${courseId}/study-duration`, {
        duration: duration
    });
}


/**
 * @description 批量更新课程章节及子任务
 * @method PUT /course/:courseId/chapters/batch
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { Array } chapters - 构造好的章节列表数据
 * @response { code: number, data: { chapters: Array<{ chapter_id: string, chapter_title: string, chapter_order: number, sub_tasks: Array<{ section_id: string, section_title: string, section_type: string, resource_path: string, description: string, section_order: number }> }> } }
 * @interactionNotes [红线] 后端处理完成后返回最终的章节列表。请求体 sub_tasks 中的 description 为必填项，无描述必须传空字符串 ""。
 */
export function update_chapters_batch(courseId, chapters) {
    return request.put(`/course/${courseId}/chapters/batch`, {chapters});
}

/**
 * @description 获取课程的章节列表（含子任务）
 * @method GET /course/:courseId/chapters
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @response { code: number, data: { chapters: Array<{ chapter_id: string, chapter_title: string, chapter_order: number, sub_tasks: Array<{ section_id: string, section_title: string, section_type: string, resource_path: string, description: string, section_order: number, is_completed?: boolean, learning_effect?: number }> }> } }
 * @interactionNotes 后端保证 chapters 及 sub_tasks 数组非空（无数据时为 []）。如果是学生身份请求，sub_tasks 会额外携带 is_completed 和 learning_effect 字段；教师身份请求则没有。
 */
export function get_chapters(courseId) {
    return request.get(`/course/${courseId}/chapters`);
}

/**
 * @description 获取小节详情（学生端使用JWT）
 * @method GET /course/:courseId/sections/:sectionId
 * @requestParams { string } courseId - 路由参数，课程 ID
 * @requestParams { string } sectionId - 路由参数，小节 ID
 * @response { code: number, data: { chapter_name: string, section_title: string, resource_type: string, resource_url: string, description: string, is_completed: boolean } }
 */
export function get_section_detail(courseId, sectionId) {
    return request.get(`/course/${courseId}/sections/${sectionId}`);
}