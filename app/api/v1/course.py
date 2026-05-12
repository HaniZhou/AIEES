from app.crud.db import db_create_course_with_students, db_get_course_detail, db_get_course_detail_for_student, \
    db_get_section_detail, db_get_chapters_with_sections, \
    db_delete_course, \
    db_batch_update_chapters, db_create_task, db_update_task, db_delete_task, db_update_gai_task, db_delete_gai_task, \
    db_create_gai_task, db_patch_course, db_get_completion_details, db_get_courses_by_teacher_page, \
    db_get_tasks_by_course, db_get_gai_tasks_by_course, db_join_course_by_code, db_get_student_courses_page, \
    db_get_gai_task_student_analysis, db_get_course_raw_records, db_get_course_ai_text, db_get_gai_task_students, \
    db_get_course_students, db_student_complete_section, db_student_feedback_section, \
    db_get_task_detail_for_student,  db_submit_gai_task, \
    db_get_task_detail_for_edit, db_get_task_review_data, db_report_study_duration, db_update_gai_task_analysis_result, \
    db_get_analysis_task_info, db_update_task_grading_result, db_submit_task_answer_for_grading
from app.model.schema.course import CourseInfo, ChapterBatchPayload, TaskCreateAndUpdate, \
    GaiTaskCreateUpdate, CourseUpdate, JoinCourseRequest, \
    SectionFeedbackRequest, TaskSubmitRequest, GaiChatRequest, GaiSubmitRequest, DurationReportRequest
from app.core.response import _success
from app.core.security import require_teacher, require_student, require_student_or_teacher, verify_token_return_payload
from app.model.schema.schema import TokenData, RoleType
from app.core.tools import generate_course_code, generate_gai_analysis_text, logger as ai_logger
from app.core.tools import write_image, remove_file
from fastapi.responses import JSONResponse
from fastapi import Depends, HTTPException, status, APIRouter, Form, UploadFile, File, Query, BackgroundTasks
import uuid
from typing import Annotated
import json
from app.Config import Prompt
from app.core.arq_jobs import process_task_grading_job
from app.core.redis_pool import get_arq_redis

router = APIRouter()


#  教师端接口 
@router.post("/create", description="创建课程")
async def create_course(
        course_name: Annotated[str, Form()],
        teaching_plan: Annotated[str, Form()],
        selected_classes: Annotated[str, Form()],
        payload: Annotated[TokenData, Depends(require_teacher)],
        cover: UploadFile | None = File(default=None),
):
    """函数目的：处理课程创建请求，包含封面文件持久化与班级关联。
    参数信息：- course_name/teaching_plan/selected_classes: Form表单数据; - payload: 教师鉴权数据; - cover: 封面文件。
    返回值：JSONResponse，包含新创建的课程ID。
    """
    db_cover_url = "covers/default.png"
    if cover is not None:
        db_cover_url = await write_image(cover)

    try:
        parsed_classes = json.loads(selected_classes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="班级数据格式错误")

    if not isinstance(parsed_classes, list) or any(not isinstance(item, str) for item in parsed_classes):
        raise HTTPException(status_code=400, detail="班级数据必须是字符串数组")

    try:
        course_id = await db_create_course_with_students(
            CourseInfo(
                course_name=course_name,
                teacher_id=payload.id,
                course_cover=db_cover_url,
                teaching_plan=teaching_plan,
                invited_code=generate_course_code(),
                is_invitation_valid=False
            ),
            parsed_classes
        )
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"code": 200, "data": {"course_id": str(course_id)}}
        )
    except Exception:
        # 如果上面发生异常，确保垃圾文件被清理
        if db_cover_url != "covers/default.png":
            await remove_file(db_cover_url)
        raise  # 重新抛出异常，让上层处理


@router.get("/get/teacher", description="教师获取课程列表")
async def get_teacher_courses(
        payload: Annotated[TokenData, Depends(require_teacher)],
        page: int = Query(default=1, ge=1, description="当前页码，从 1 开始"),
):
    """函数目的：分页获取当前教师创建的课程列表。
    参数信息：- payload: 教师鉴权数据; - page: 页码。
    返回值：JSONResponse，包含课程字典列表。
    """
    courses = await db_get_courses_by_teacher_page(payload.id, page)
    return _success({"courses": courses})


@router.delete("/{course_id}", description="删除课程")
async def delete_course(
        course_id: uuid.UUID,
        payload: Annotated[TokenData, Depends(require_teacher)]
):
    """函数目的：删除指定课程及其关联的所有资源。
    参数信息：- course_id: 课程UUID; - payload: 教师鉴权数据。
    返回值：JSONResponse，空数据成功信封。
    """
    await db_delete_course(payload.id, course_id)
    return _success({})


@router.put("/{course_id}/chapters/batch", description="批量新增/修改/删除课程章节及子任务")
async def batch_update_chapters(
        course_id: uuid.UUID,
        payload: ChapterBatchPayload,
        token_data: Annotated[TokenData, Depends(require_teacher)]
):
    """函数目的：批量同步课程的章节与小节树结构。
    参数信息：- course_id: 课程UUID; - payload: 章节树载荷; - token_data: 教师鉴权数据。
    返回值：JSONResponse，包含最新章节树结构。
    """
    chapters = await db_batch_update_chapters(course_id, payload, token_data.id)
    return _success({"chapters": chapters})


@router.get("/{course_id}/students", description="获取课程已加入的全部学生")
async def get_course_students(
        course_id: uuid.UUID,
        token_data: Annotated[TokenData, Depends(require_teacher)],
):
    """函数目的：获取课程下所有已加入学生的基础信息列表。
    参数信息：- course_id: 课程UUID; - token_data: 教师鉴权数据。
    返回值：JSONResponse，包含学生ID和姓名列表。
    """
    students = await db_get_course_students(course_id, token_data.id)
    return _success({"students": students})


@router.post("/{course_id}/tasks", description="创建测验任务")
async def create_task(
        course_id: uuid.UUID,
        payload: TaskCreateAndUpdate,
        token_data: Annotated[TokenData, Depends(require_teacher)]
):
    """函数目的：创建课程下的测验任务。
    参数信息：- course_id: 课程UUID; - payload: 测验任务载荷; - token_data: 教师鉴权数据。
    返回值：JSONResponse，包含创建后的任务详情。
    """
    task = await db_create_task(course_id, token_data.id, payload.model_dump())
    return _success(task)


@router.put("/{course_id}/tasks/{task_id}", description="更新测验任务")
async def update_task(
        course_id: uuid.UUID,
        task_id: int,
        payload: TaskCreateAndUpdate,
        token_data: Annotated[TokenData, Depends(require_teacher)]
):
    """函数目的：更新已有的测验任务内容及答案。
    参数信息：- course_id: 课程UUID; - task_id: 任务ID; - payload: 测验任务载荷; - token_data: 教师鉴权数据。
    返回值：JSONResponse，包含更新后的任务详情。
    """
    task = await db_update_task(course_id, task_id, token_data.id, payload.model_dump())
    return _success(task)


@router.delete("/{course_id}/tasks/{task_id}", description="删除测验任务")
async def delete_task(
        course_id: uuid.UUID,
        task_id: int,
        token_data: Annotated[TokenData, Depends(require_teacher)]
):
    """函数目的：删除指定的测验任务。
    参数信息：- course_id: 课程UUID; - task_id: 任务ID; - token_data: 教师鉴权数据。
    返回值：JSONResponse，空数据成功信封。
    """
    await db_delete_task(course_id, task_id, token_data.id)
    return _success({})


@router.post("/{course_id}/gai-tasks", description="创建 GAI 探索任务")
async def create_gai_task(
        course_id: uuid.UUID,
        payload: GaiTaskCreateUpdate,
        token_data: Annotated[TokenData, Depends(require_teacher)]
):
    """函数目的：创建 GAI 对话式探究任务。
    参数信息：- course_id: 课程UUID; - payload: GAI任务载荷; - token_data: 教师鉴权数据。
    返回值：JSONResponse，包含创建后的任务详情。
    """
    task = await db_create_gai_task(course_id, token_data.id, payload.model_dump())
    return _success(task)


@router.get("/{course_id}/gai-tasks/{task_id}/students", description="获取 GAI 任务学生列表及完成状态")
async def get_gai_task_students(
        course_id: uuid.UUID,
        task_id: int,
        token_data: Annotated[TokenData, Depends(require_teacher)],
):
    """函数目的：获取指定 GAI 任务下所有学生的完成状态视图。
    参数信息：- course_id: 课程UUID; - task_id: 任务ID; - token_data: 教师鉴权数据。
    返回值：JSONResponse，包含学生列表及完成布尔值。
    """
    students = await db_get_gai_task_students(course_id, task_id, token_data.id)
    return _success({"students": students})


@router.put("/{course_id}/gai-tasks/{task_id}", description="更新 GAI 探索任务")
async def update_gai_task(
        course_id: uuid.UUID,
        task_id: int,
        payload: GaiTaskCreateUpdate,
        token_data: Annotated[TokenData, Depends(require_teacher)]
):
    """函数目的：更新 GAI 探究任务的配置参数。
    参数信息：- course_id: 课程UUID; - task_id: 任务ID; - payload: GAI任务载荷; - token_data: 教师鉴权数据。
    返回值：JSONResponse，包含更新后的任务详情。
    """
    task = await db_update_gai_task(course_id, task_id, token_data.id, payload.model_dump())
    return _success(task)


@router.delete("/{course_id}/gai-tasks/{task_id}", description="删除 GAI 探索任务")
async def delete_gai_task(
        course_id: uuid.UUID,
        task_id: int,
        token_data: Annotated[TokenData, Depends(require_teacher)]
):
    """函数目的：删除指定的 GAI 探究任务。
    参数信息：- course_id: 课程UUID; - task_id: 任务ID; - token_data: 教师鉴权数据。
    返回值：JSONResponse，空数据成功信封。
    """
    await db_delete_gai_task(course_id, task_id, token_data.id)
    return _success({})


@router.patch("/{course_id}", description="局部更新课程信息(如切换邀请码有效性)")
async def patch_course(
        course_id: uuid.UUID,
        payload: CourseUpdate,
        token_data: Annotated[TokenData, Depends(require_teacher)]
):
    """函数目的：局部更新课程的基本信息字段。
    参数信息：- course_id: 课程UUID; - payload: 局部更新载荷; - token_data: 教师鉴权数据。
    返回值：JSONResponse，包含更新后的课程详情。
    """
    update_data = payload.model_dump(exclude_none=True)
    course = await db_patch_course(course_id, token_data.id, update_data)
    return _success(course)


@router.get("/{course_id}/completion-details", description="获取章节/任务的全班完成原始数据")
async def get_completion_details(
        token_data: Annotated[TokenData, Depends(require_teacher)],
        course_id: uuid.UUID,
        type: str = Query(..., pattern="^(section|task)$", description="类型：section 或 task"),
        target_id: int = Query(..., description="对应的 section_id 或 task_id"),
):
    """函数目的：获取教师看板中某个章节或任务的全班完成情况统计。
    参数信息：- token_data: 教师鉴权数据; - course_id: 课程UUID; - type/target_id: 资源定位参数。
    返回值：JSONResponse，包含学生完成明细列表。
    """
    records = await db_get_completion_details(course_id, type, target_id, token_data.id)
    return _success({"student_records": records})


@router.get("/{course_id}/gai-tasks/{task_id}/student-analysis", description="获取学生在某个 GAI 任务中的对话与分析")
async def get_gai_task_student_analysis(
        course_id: uuid.UUID,
        task_id: int,
        token_data: Annotated[TokenData, Depends(require_teacher)],
        student_id: str = Query(..., description="学生 ID"),
):
    """函数目的：获取教师查看指定学生在某 GAI 任务中的对话记录与 AI 分析结果。
    参数信息：- course_id: 课程UUID; - task_id: 任务ID; - token_data: 教师鉴权数据; - student_id: 目标学生ID。
    返回值：JSONResponse，包含对话历史及分析文本。
    """
    result = await db_get_gai_task_student_analysis(course_id, task_id, token_data.id, str(student_id))
    return _success(result)


@router.get("/{course_id}/analysis/raw-records", description="获取课程下所有学生的原始完成记录")
async def get_analysis_raw_records(
        course_id: uuid.UUID,
        token_data: Annotated[TokenData, Depends(require_teacher)]
):
    """函数目的：聚合获取课程下所有学生的原始完成记录，供高级分析使用。
    参数信息：- course_id: 课程UUID; - token_data: 教师鉴权数据。
    返回值：JSONResponse，包含聚合后的原始记录字典。
    """
    records = await db_get_course_raw_records(course_id, token_data.id)
    return _success({"records": records})


@router.get("/{course_id}/analysis/ai-text", description="获取课程学生学习 AI 分析文本")
async def get_analysis_ai_text_for_student_study(
        course_id: uuid.UUID,
        token_data: Annotated[TokenData, Depends(require_teacher)],
        student_id: str = Query(default="all", description="all 或具体学生 ID"),
):
    """函数目的：获取课程的 AI 学情分析文本（全班或个人）。
    参数信息：- course_id: 课程UUID; - token_data: 教师鉴权数据; - student_id: 目标学生ID或'all'。
    返回值：JSONResponse，包含分析文本内容。
    """
    description = await db_get_course_ai_text(course_id, token_data.id, student_id)
    return _success({"description": description})


#  学生端接口 
@router.get("/student", description="获取学生已加入课程")
async def get_student_courses(
        payload: Annotated[TokenData, Depends(verify_token_return_payload)],
        page: int = Query(default=1, ge=1, description="页码，从1开始")
):
    """函数目的：分页获取当前学生已加入的课程列表。
    参数信息：- payload: 通用鉴权数据; - page: 页码。
    返回值：JSONResponse，包含课程列表及是否有下一页标识。
    """
    if payload.role != RoleType.student:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    data = await db_get_student_courses_page(payload.id, page)
    return _success(data)


@router.post("/join", description="加入班级（提交邀请码）")
async def join_course(
        req: JoinCourseRequest,
        payload: Annotated[TokenData, Depends(verify_token_return_payload)]
):
    """函数目的：处理学生通过邀请码加入课程的操作。
    参数信息：- req: 包含邀请码的请求体; - payload: 通用鉴权数据。
    返回值：JSONResponse，包含加入成功的课程ID。
    """
    if payload.role != RoleType.student:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅学生可加入课程")
    course_id = await db_join_course_by_code(payload.id, req.invite_code)
    return _success({"course_id": course_id})


@router.post("/{course_id}/sections/{section_id}/complete", description="学生标记学习资源完成")
async def student_complete_section(
        course_id: uuid.UUID,
        section_id: int,
        token_data: Annotated[TokenData, Depends(require_student)]
):
    """函数目的：将指定小节标记为当前学生已完成状态。
    参数信息：- course_id: 课程UUID; - section_id: 小节ID; - token_data: 学生鉴权数据。
    返回值：JSONResponse，空数据成功信封。
    """
    await db_student_complete_section(course_id, section_id, token_data.id)
    return _success({})


@router.post("/{course_id}/sections/{section_id}/feedback", description="学生提交学习难度反馈")
async def student_feedback_section(
        course_id: uuid.UUID,
        section_id: int,
        payload: SectionFeedbackRequest,
        token_data: Annotated[TokenData, Depends(require_student)]
):
    """函数目的：接收学生对特定小节的学习难度反馈。
    参数信息：- course_id: 课程UUID; - section_id: 小节ID; - payload: 难度载荷; - token_data: 学生鉴权数据。
    返回值：JSONResponse，空数据成功信封。
    """
    await db_student_feedback_section(course_id, section_id, token_data.id, payload.difficulty)
    return _success({})


@router.post("/{course_id}/tasks/{task_id}/submit", description="学生提交测验答案")
async def submit_task_answer(
        course_id: uuid.UUID,
        task_id: int,
        payload: TaskSubmitRequest,
        token_data: Annotated[TokenData, Depends(require_student)]
):
    """函数目的：接收学生提交，落库后交由 ARQ 后台异步评分，立即返回评分中状态。
    参数信息：- course_id: 课程UUID; - task_id: 任务ID; - payload: 包含答案数组; - token_data: 学生鉴权数据。
    返回值：JSONResponse，包含 task_id 和 grading 状态。
    """
    # 1. 基础业务拦截与记录创建
    completion_id = await db_submit_task_answer_for_grading(
        course_id, task_id, token_data.id, payload.model_dump()["answers"]
    )

    # 2. 将耗时任务推入 ARQ 队列 (使用专用的 ArqRedis 客户端)
    try:
        arq_client = get_arq_redis()
        await arq_client.enqueue_job(
            process_task_grading_job.__name__,
            task_completion_id=completion_id,
            course_id=str(course_id),
            student_id=token_data.id,
            task_id=task_id
        )
    except Exception as arq_err:
        # 队列推送失败必须回滚数据库状态，避免任务卡死
        await db_update_task_grading_result(completion_id, 0, f"评分队列异常: {str(arq_err)}")
        # 将网络/中间件异常转化为规范的 502 上游错误
        raise HTTPException(status_code=502, detail="评分服务暂不可用，请稍后重试")

    return _success({"task_id": task_id, "status": "grading"})


@router.get("/{course_id}/tasks/{task_id}/review", description="获取学生已提交任务的批改回顾详情")
async def get_task_review(
        course_id: uuid.UUID,
        task_id: int,
        token_data: Annotated[TokenData, Depends(require_student)]
) -> JSONResponse:
    """函数目的：处理学生端获取任务批改回顾详情的请求。
    参数信息：- course_id: 课程UUID; - task_id: 任务ID; - token_data: 学生鉴权数据。
    返回值：JSONResponse，包含得分、AI分析及逐题作答对照。
    """
    data = await db_get_task_review_data(course_id, task_id, token_data.id)
    return _success(data)


@router.post("/{course_id}/gai-tasks/{task_id}/submit", description="学生提交 GAI 探究任务")
async def submit_gai_task(
        course_id: uuid.UUID,
        task_id: int,
        payload: GaiSubmitRequest,
        token_data: Annotated[TokenData, Depends(require_student)],
        background_tasks: BackgroundTasks
):
    """函数目的：接收学生 GAI 对话提交，落库并投递至后台执行 AI 分析。
    参数信息：- course_id: 课程UUID; - task_id: 任务ID; - payload: 对话消息列表; - token_data: 学生鉴权数据; - background_tasks: FastAPI后台任务器。
    返回值：JSONResponse，空数据成功信封。
    """
    completion_id = await db_submit_gai_task(course_id, task_id, token_data.id, payload.messages)
    background_tasks.add_task(
        _execute_gai_analysis, task_id=task_id, completion_id=completion_id, messages=payload.messages
    )
    return _success({})


async def _execute_gai_analysis(task_id: int, completion_id: int, messages: list) -> None:
    """函数目的：后台异步执行大模型学情分析并持久化结果。
    参数信息：- task_id: 关联的 GAI 任务 ID; - completion_id: 待更新的提交记录主键 ID; - messages: 原始对话列表。
    返回值：无。
    """
    try:
        task_info = await db_get_analysis_task_info(task_id)
        if not task_info:
            await db_update_gai_task_analysis_result(completion_id, "AI分析失败：任务配置丢失")
            return

        system_prompt = (
            f"{Prompt.TEACHER_ANALYSIS_SYSTEM_PROMPT}\n\n"
            f"【任务描述】：{task_info['task_description']}\n"
            f"【分析要求】：{task_info['analysis_description']}\n"
            f"【评价标准】：{task_info['evaluation_criterion']}"
        )
        user_content = "\n".join([f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" for msg in messages])
        analysis_text = await generate_gai_analysis_text(system_prompt, user_content)
        await db_update_gai_task_analysis_result(completion_id, analysis_text)
    except Exception as e:
        ai_logger.error(
            f"GAI analysis execution failed, task_id={task_id}, completion_id={completion_id}, error: {str(e)}")
        await db_update_gai_task_analysis_result(completion_id, "AI分析失败，请稍后重试")


#  师生共用接口 
@router.get("/{course_id}", description="获取课程详细信息")
async def get_course_detail(
        course_id: uuid.UUID,
        payload: Annotated[TokenData, Depends(require_student_or_teacher)]
):
    """函数目的：根据角色获取课程的详细信息视图。
    参数信息：- course_id: 课程UUID; - payload: 通用师生鉴权数据。
    返回值：JSONResponse，包含课程详情字典。
    """
    if payload.role == RoleType.teacher:
        detail = await db_get_course_detail(course_id, payload.id)
    else:
        detail = await db_get_course_detail_for_student(course_id, payload.id)
    if not detail:
        raise HTTPException(status_code=404, detail="课程不存在")
    return _success(detail)


@router.get("/{course_id}/chapters", description="获取课程章节及子任务列表")
async def get_course_chapters(
        course_id: uuid.UUID,
        payload: Annotated[TokenData, Depends(require_student_or_teacher)]
):
    """函数目的：获取课程下的章节及小节树结构，学生端附带完成状态。
    参数信息：- course_id: 课程UUID; - payload: 通用师生鉴权数据。
    返回值：JSONResponse，包含章节树列表。
    """
    student_id = payload.id if payload.role == RoleType.student else None
    teacher_id = payload.id if payload.role == RoleType.teacher else None
    chapters = await db_get_chapters_with_sections(course_id, student_id=student_id, teacher_id=teacher_id)
    return _success({"chapters": chapters})


@router.get("/{course_id}/tasks", description="获取课程的测验任务列表")
async def get_course_tasks(
        course_id: uuid.UUID,
        token_data: Annotated[TokenData, Depends(require_student_or_teacher)]
):
    """函数目的：获取课程下的测验任务摘要列表。
    参数信息：- course_id: 课程UUID; - token_data: 通用师生鉴权数据。
    返回值：JSONResponse，包含任务摘要列表。
    """
    tasks = await db_get_tasks_by_course(course_id, token_data.id, token_data.role)
    return _success({"tasks": tasks})


@router.get("/{course_id}/gai-tasks", description="获取课程的 GAI 任务列表")
async def get_course_gai_tasks(
        course_id: uuid.UUID,
        token_data: Annotated[TokenData, Depends(require_student_or_teacher)]
):
    """函数目的：获取课程下的 GAI 探究任务摘要列表。
    参数信息：- course_id: 课程UUID; - token_data: 通用师生鉴权数据。
    返回值：JSONResponse，包含 GAI 任务摘要列表。
    """
    gai_tasks = await db_get_gai_tasks_by_course(course_id, token_data.id, token_data.role)
    return _success({"gai_tasks": gai_tasks})


@router.get("/{course_id}/tasks/{task_id}", description="获取测验任务的题目详情")
async def get_task_detail(
        course_id: uuid.UUID,
        task_id: int,
        token_data: Annotated[TokenData, Depends(require_student_or_teacher)]
):
    """函数目的：学生获取测验任务的题目详情（不含标答）。
    参数信息：- course_id: 课程UUID; - task_id: 任务ID; - token_data: 通用师生鉴权数据。
    返回值：JSONResponse，包含题目及学生历史作答状态。
    """
    student_id = token_data.id if token_data.role == RoleType.student else None
    task_detail = await db_get_task_detail_for_student(course_id, task_id, student_id)
    if not task_detail:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _success(task_detail)


@router.get("/{course_id}/sections/{section_id}", description="获取小节学习详情")
async def get_section_detail(
        course_id: uuid.UUID,
        section_id: int,
        token_data: Annotated[TokenData, Depends(require_student)]
):
    """函数目的：学生获取特定小节的学习资源详情及完成状态。
    参数信息：- course_id: 课程UUID; - section_id: 小节ID; - token_data: 学生鉴权数据。
    返回值：JSONResponse，包含资源路径、类型及完成状态。
    """
    detail = await db_get_section_detail(course_id, section_id, token_data.id)
    if not detail:
        raise HTTPException(status_code=404, detail="小节不存在")
    return _success(detail)


@router.get("/{course_id}/tasks/{task_id}/edit", description="教师获取任务详情（含答案）用于编辑")
async def get_task_detail_for_edit(
        course_id: uuid.UUID,
        task_id: int,
        payload: Annotated[TokenData, Depends(require_teacher)]
) -> JSONResponse:
    """函数目的：处理教师端获取特定任务编辑详情的请求，返回包含正确答案的完整题目结构。
    参数信息：- course_id: 课程UUID; - task_id: 任务ID; - payload: 教师鉴权数据。
    返回值：JSONResponse，包含完整题目及答案结构。
    """
    data = await db_get_task_detail_for_edit(course_id, task_id, payload.id)
    return _success(data)


@router.post("/{course_id}/study-duration", description="上报学生增量学习时长")
async def report_study_duration(
        course_id: uuid.UUID,
        body: DurationReportRequest,
        token_data: Annotated[TokenData, Depends(require_student)]
):
    """函数目的：处理前端分片发送的学习时长上报请求，委托 DB 层完成原子累加。
    参数信息：- course_id: 课程UUID; - body: 包含本次学习的正整数秒数; - token_data: 学生鉴权数据。
    返回值：JSONResponse，统一成功信封。
    """
    await db_report_study_duration(course_id, token_data.id, body.duration)
    return _success({})