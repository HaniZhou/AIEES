import json
import uuid
from typing import Annotated

from fastapi.responses import JSONResponse

from app.api.dependencies import require_student, require_student_or_teacher, require_teacher
from app.common.response import response_success
from app.common.tools import generate_course_code, remove_file, write_image
from app.core.database import db
from app.schema.chapter import ChapterBatchPayload, SectionFeedbackRequest
from app.schema.course import CourseInfo, CourseUpdate, JoinCourseRequest
from app.schema.enums import RoleType
from app.schema.gai_task import GaiSubmitRequest, GaiTaskCreateUpdate
from app.schema.task import DurationReportRequest, TaskCreateAndUpdate, TaskSubmitRequest
from app.schema.user import TokenData
from app.service.analysis_service import AnalysisService
from app.service.course_service import CourseService
from app.service.organization_service import OrganizationService
from app.service.student_service import StudentService
from app.service.task_service import TaskService
from app.task.job.grading import process_task_grading_job
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

router = APIRouter()


#  教师端接口
@router.post("/create", description="创建课程")
async def create_course(
    course_name: Annotated[str, Form()],
    teaching_plan: Annotated[str, Form()],
    selected_classes: Annotated[str, Form()],
    payload: Annotated[TokenData, Depends(require_teacher)],
    cover: UploadFile | None = File(default=None),
    course_svc: CourseService = Depends(CourseService),
):
    db_cover_url = "covers/default.png"
    if cover is not None:
        db_cover_url = await write_image(cover)

    try:
        parsed_classes = json.loads(selected_classes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="班级数据格式错误") from None

    if not isinstance(parsed_classes, list) or any(not isinstance(item, str) for item in parsed_classes):
        raise HTTPException(status_code=400, detail="班级数据必须是字符串数组")

    try:
        course_id = await course_svc.create_course_with_students(
            CourseInfo(
                course_name=course_name,
                teacher_id=payload.id,
                course_cover=db_cover_url,
                teaching_plan=teaching_plan,
                invited_code=generate_course_code(),
                is_invitation_valid=False,
            ),
            parsed_classes,
        )
        return JSONResponse(
            status_code=status.HTTP_201_CREATED, content={"code": 200, "data": {"course_id": str(course_id)}}
        )
    except Exception:
        if db_cover_url != "covers/default.png":
            await remove_file(db_cover_url)
        raise


@router.get("/get/teacher", description="教师获取课程列表")
async def get_teacher_courses(
    payload: Annotated[TokenData, Depends(require_teacher)],
    page: int = Query(default=1, ge=1, description="当前页码，从 1 开始"),
    course_svc: CourseService = Depends(CourseService),
):
    courses = await course_svc.get_teacher_courses_page(payload.id, page)
    return response_success(courses)


@router.delete("/{course_id}", description="删除课程")
async def delete_course(
    course_id: uuid.UUID,
    payload: Annotated[TokenData, Depends(require_teacher)],
    course_svc: CourseService = Depends(CourseService),
):
    await course_svc.delete_course(payload.id, course_id)
    return response_success({})


@router.put("/{course_id}/chapters/batch", description="批量新增/修改/删除课程章节及子任务")
async def batch_update_chapters(
    course_id: uuid.UUID,
    payload: ChapterBatchPayload,
    token_data: Annotated[TokenData, Depends(require_teacher)],
    course_svc: CourseService = Depends(CourseService),
):
    chapters = await course_svc.batch_update_chapters(course_id, payload, token_data.id)
    return response_success({"chapters": chapters})


@router.get("/{course_id}/students", description="获取课程已加入的全部学生")
async def get_course_students(
    course_id: uuid.UUID,
    token_data: Annotated[TokenData, Depends(require_teacher)],
    course_svc: CourseService = Depends(CourseService),
):
    students = await course_svc.get_course_students(course_id, token_data.id)
    return response_success({"students": students})


@router.post("/{course_id}/tasks", description="创建测验任务")
async def create_task(
    course_id: uuid.UUID,
    payload: TaskCreateAndUpdate,
    token_data: Annotated[TokenData, Depends(require_teacher)],
    course_svc: CourseService = Depends(CourseService),
):
    task = await course_svc.create_task(course_id, token_data.id, payload.model_dump())
    return response_success(task)


@router.put("/{course_id}/tasks/{task_id}", description="更新测验任务")
async def update_task(
    course_id: uuid.UUID,
    task_id: int,
    payload: TaskCreateAndUpdate,
    token_data: Annotated[TokenData, Depends(require_teacher)],
    course_svc: CourseService = Depends(CourseService),
):
    task = await course_svc.update_task(course_id, task_id, token_data.id, payload.model_dump())
    return response_success(task)


@router.delete("/{course_id}/tasks/{task_id}", description="删除测验任务")
async def delete_task(
    course_id: uuid.UUID,
    task_id: int,
    token_data: Annotated[TokenData, Depends(require_teacher)],
    course_svc: CourseService = Depends(CourseService),
):
    await course_svc.delete_task(course_id, task_id, token_data.id)
    return response_success({})


@router.post("/{course_id}/gai-tasks", description="创建 GAI 探索任务")
async def create_gai_task(
    course_id: uuid.UUID,
    payload: GaiTaskCreateUpdate,
    token_data: Annotated[TokenData, Depends(require_teacher)],
    course_svc: CourseService = Depends(CourseService),
):
    task = await course_svc.create_gai_task(course_id, token_data.id, payload.model_dump())
    return response_success(task)


@router.get("/{course_id}/gai-tasks/{task_id}/students", description="获取 GAI 任务学生列表及完成状态")
async def get_gai_task_students(
    course_id: uuid.UUID,
    task_id: int,
    token_data: Annotated[TokenData, Depends(require_teacher)],
    org_svc: OrganizationService = Depends(OrganizationService),
):
    students = await org_svc.get_gai_task_students(course_id, task_id, token_data.id)
    return response_success({"students": students})


@router.put("/{course_id}/gai-tasks/{task_id}", description="更新 GAI 探索任务")
async def update_gai_task(
    course_id: uuid.UUID,
    task_id: int,
    payload: GaiTaskCreateUpdate,
    token_data: Annotated[TokenData, Depends(require_teacher)],
    course_svc: CourseService = Depends(CourseService),
):
    task = await course_svc.update_gai_task(course_id, task_id, token_data.id, payload.model_dump())
    return response_success(task)


@router.delete("/{course_id}/gai-tasks/{task_id}", description="删除 GAI 探索任务")
async def delete_gai_task(
    course_id: uuid.UUID,
    task_id: int,
    token_data: Annotated[TokenData, Depends(require_teacher)],
    course_svc: CourseService = Depends(CourseService),
):
    await course_svc.delete_gai_task(course_id, task_id, token_data.id)
    return response_success({})


@router.patch("/{course_id}", description="局部更新课程信息(如切换邀请码有效性)")
async def patch_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    token_data: Annotated[TokenData, Depends(require_teacher)],
    course_svc: CourseService = Depends(CourseService),
):
    update_data = payload.model_dump(exclude_none=True)
    course = await course_svc.patch_course(course_id, token_data.id, update_data)
    return response_success(course)


@router.get("/{course_id}/completion-details", description="获取章节/任务的全班完成原始数据")
async def get_completion_details(
    token_data: Annotated[TokenData, Depends(require_teacher)],
    course_id: uuid.UUID,
    type: str = Query(..., pattern="^(section|task)$", description="类型：section 或 task"),
    target_id: int = Query(..., description="对应的 section_id 或 task_id"),
    course_svc: CourseService = Depends(CourseService),
):
    records = await course_svc.get_completion_details(course_id, type, target_id, token_data.id)
    return response_success({"student_records": records})


@router.get("/{course_id}/gai-tasks/{task_id}/student-analysis", description="获取学生在某个 GAI 任务中的对话与分析")
async def get_gai_task_student_analysis(
    course_id: uuid.UUID,
    task_id: int,
    token_data: Annotated[TokenData, Depends(require_teacher)],
    student_id: str = Query(..., description="学生 ID"),
    analysis_svc: AnalysisService = Depends(AnalysisService),
):
    result = await analysis_svc.get_gai_task_student_analysis(course_id, task_id, token_data.id, str(student_id))
    return response_success(result)


@router.get("/{course_id}/analysis/raw-records", description="获取课程下所有学生的原始完成记录")
async def get_analysis_raw_records(
    course_id: uuid.UUID,
    token_data: Annotated[TokenData, Depends(require_teacher)],
    course_svc: CourseService = Depends(CourseService),
):
    records = await course_svc.get_course_raw_records(course_id, token_data.id)
    return response_success({"records": records})


@router.get("/{course_id}/analysis/ai-text", description="获取课程学生学习 AI 分析文本")
async def get_analysis_ai_text_for_student_study(
    course_id: uuid.UUID,
    token_data: Annotated[TokenData, Depends(require_teacher)],
    student_id: str = Query(default="all", description="all 或具体学生 ID"),
    course_svc: CourseService = Depends(CourseService),
):
    description = await course_svc.get_course_ai_text(course_id, token_data.id, student_id)
    return response_success({"description": description})


#  学生端接口
@router.get("/student", description="获取学生已加入课程")
async def get_student_courses(
    payload: Annotated[TokenData, Depends(require_student)],
    page: int = Query(default=1, ge=1, description="页码，从1开始"),
    course_svc: CourseService = Depends(CourseService),
):
    data = await course_svc.get_student_courses_page(payload.id, page)
    return response_success(data)


@router.post("/join", description="加入班级（提交邀请码）")
async def join_course(
    req: JoinCourseRequest,
    payload: Annotated[TokenData, Depends(require_student)],
    course_svc: CourseService = Depends(CourseService),
):
    course_id = await course_svc.join_course_by_code(payload.id, req.invite_code)
    return response_success({"course_id": course_id})


@router.post("/{course_id}/sections/{section_id}/complete", description="学生标记学习资源完成")
async def student_complete_section(
    course_id: uuid.UUID,
    section_id: int,
    token_data: Annotated[TokenData, Depends(require_student)],
    task_svc: TaskService = Depends(TaskService),
):
    await task_svc.student_complete_section(course_id, section_id, token_data.id)
    return response_success({})


@router.post("/{course_id}/sections/{section_id}/feedback", description="学生提交学习难度反馈")
async def student_feedback_section(
    course_id: uuid.UUID,
    section_id: int,
    payload: SectionFeedbackRequest,
    token_data: Annotated[TokenData, Depends(require_student)],
    task_svc: TaskService = Depends(TaskService),
):
    await task_svc.student_feedback_section(course_id, section_id, token_data.id, payload.difficulty)
    return response_success({})


@router.post("/{course_id}/tasks/{task_id}/submit", description="学生提交测验答案")
async def submit_task_answer(
    course_id: uuid.UUID,
    task_id: int,
    payload: TaskSubmitRequest,
    token_data: Annotated[TokenData, Depends(require_student)],
    task_svc: TaskService = Depends(TaskService),
):
    completion_id = await task_svc.submit_task_answer(
        course_id, task_id, token_data.id, payload.model_dump()["answers"]
    )
    await task_svc.session.commit()

    try:
        await process_task_grading_job.kiq(
            task_completion_id=completion_id, course_id=str(course_id), student_id=token_data.id, task_id=task_id
        )
    except Exception as exc:
        # 独立会话落库：不受本请求事务 rollback 影响，保证评分状态可恢复
        async with db.async_session_factory() as fallback_session:
            fallback_svc = TaskService(session=fallback_session)
            await fallback_svc.update_grading_result(completion_id, 0, f"评分队列异常: {str(exc)}")
            await fallback_session.commit()
        raise HTTPException(status_code=502, detail="评分服务暂不可用，请稍后重试") from exc

    return response_success({"task_id": task_id, "status": "grading"})


@router.get("/{course_id}/tasks/{task_id}/review", description="获取学生已提交任务的批改回顾详情")
async def get_task_review(
    course_id: uuid.UUID,
    task_id: int,
    token_data: Annotated[TokenData, Depends(require_student)],
    task_svc: TaskService = Depends(TaskService),
) -> JSONResponse:
    data = await task_svc.get_task_review_data(course_id, task_id, token_data.id)
    return response_success(data)


@router.post("/{course_id}/gai-tasks/{task_id}/submit", description="学生提交 GAI 探究任务")
async def submit_gai_task(
    course_id: uuid.UUID,
    task_id: int,
    payload: GaiSubmitRequest,
    token_data: Annotated[TokenData, Depends(require_student)],
    task_svc: TaskService = Depends(TaskService),
):
    from app.task.job.gai_analysis import process_gai_analysis_job

    completion_id = await task_svc.submit_gai_task(course_id, task_id, token_data.id, payload.messages)
    await task_svc.session.commit()
    try:
        await process_gai_analysis_job.kiq(
            task_id=task_id,
            completion_id=completion_id,
            messages=payload.messages,
        )
    except Exception as exc:
        # 独立会话落库：不受本请求事务 rollback 影响，保证分析状态可恢复
        async with db.async_session_factory() as fallback_session:
            fallback_svc = AnalysisService(session=fallback_session)
            await fallback_svc.update_gai_task_analysis_result(completion_id, f"分析队列异常: {str(exc)}")
            await fallback_session.commit()
        raise HTTPException(status_code=502, detail="分析服务暂不可用，请稍后重试") from exc

    return response_success({})


#  师生共用接口
@router.get("/{course_id}", description="获取课程详细信息")
async def get_course_detail(
    course_id: uuid.UUID,
    payload: Annotated[TokenData, Depends(require_student_or_teacher)],
    course_svc: CourseService = Depends(CourseService),
    student_svc: StudentService = Depends(StudentService),
):
    if payload.role == RoleType.teacher:
        detail = await course_svc.get_course_detail(course_id, payload.id)
    else:
        detail = await student_svc.get_course_detail_for_student(course_id, payload.id)
    if not detail:
        raise HTTPException(status_code=404, detail="课程不存在")
    return response_success(detail)


@router.get("/{course_id}/chapters", description="获取课程章节及子任务列表")
async def get_course_chapters(
    course_id: uuid.UUID,
    payload: Annotated[TokenData, Depends(require_student_or_teacher)],
    course_svc: CourseService = Depends(CourseService),
):
    student_id = payload.id if payload.role == RoleType.student else None
    teacher_id = payload.id if payload.role == RoleType.teacher else None
    chapters = await course_svc.get_chapters_with_sections(course_id, student_id=student_id, teacher_id=teacher_id)
    return response_success({"chapters": chapters})


@router.get("/{course_id}/tasks", description="获取课程的测验任务列表")
async def get_course_tasks(
    course_id: uuid.UUID,
    token_data: Annotated[TokenData, Depends(require_student_or_teacher)],
    task_svc: TaskService = Depends(TaskService),
):
    tasks = await task_svc.get_tasks_by_course(course_id, token_data.id, token_data.role)
    return response_success({"tasks": tasks})


@router.get("/{course_id}/gai-tasks", description="获取课程的 GAI 任务列表")
async def get_course_gai_tasks(
    course_id: uuid.UUID,
    token_data: Annotated[TokenData, Depends(require_student_or_teacher)],
    analysis_svc: AnalysisService = Depends(AnalysisService),
):
    gai_tasks = await analysis_svc.get_gai_tasks_by_course(course_id, token_data.id, token_data.role)
    return response_success({"gai_tasks": gai_tasks})


@router.get("/{course_id}/tasks/{task_id}", description="获取测验任务的题目详情")
async def get_task_detail(
    course_id: uuid.UUID,
    task_id: int,
    token_data: Annotated[TokenData, Depends(require_student_or_teacher)],
    task_svc: TaskService = Depends(TaskService),
):
    student_id = token_data.id if token_data.role == RoleType.student else None
    task_detail = await task_svc.get_task_detail_for_student(course_id, task_id, student_id)
    if not task_detail:
        raise HTTPException(status_code=404, detail="任务不存在")
    return response_success(task_detail)


@router.get("/{course_id}/sections/{section_id}", description="获取小节学习详情")
async def get_section_detail(
    course_id: uuid.UUID,
    section_id: int,
    token_data: Annotated[TokenData, Depends(require_student)],
    student_svc: StudentService = Depends(StudentService),
):
    detail = await student_svc.get_section_detail(course_id, section_id, token_data.id)
    if not detail:
        raise HTTPException(status_code=404, detail="小节不存在")
    return response_success(detail)


@router.get("/{course_id}/tasks/{task_id}/edit", description="教师获取任务详情（含答案）用于编辑")
async def get_task_detail_for_edit(
    course_id: uuid.UUID,
    task_id: int,
    payload: Annotated[TokenData, Depends(require_teacher)],
    task_svc: TaskService = Depends(TaskService),
) -> JSONResponse:
    data = await task_svc.get_task_detail_for_edit(course_id, task_id, payload.id)
    return response_success(data)


@router.post("/{course_id}/study-duration", description="上报学生增量学习时长")
async def report_study_duration(
    course_id: uuid.UUID,
    body: DurationReportRequest,
    token_data: Annotated[TokenData, Depends(require_student)],
    student_svc: StudentService = Depends(StudentService),
):
    await student_svc.report_study_duration(course_id, token_data.id, body.duration)
    return response_success({})
