import uuid
from typing import Annotated

from fastapi.responses import JSONResponse

from app.api.dependencies import require_student, require_teacher
from app.common.response import response_success
from app.schema.user import TokenData
from app.service.student_service import StudentService
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/weekly-study", description="学生获取本周每日学习时长(秒)")
async def get_student_weekly_study(
    payload: Annotated[TokenData, Depends(require_student)],
    student_svc: StudentService = Depends(StudentService),
) -> JSONResponse:
    seconds = await student_svc.get_weekly_study(payload.id)
    return response_success({"daily_seconds": seconds})


@router.get(
    "/{student_id}/course/{course_id}/weekly-study", description="教师获取指定学生在某课程的本周每日学习时长(秒)"
)
async def get_student_weekly_study_by_teacher(
    student_id: str,
    course_id: uuid.UUID,
    payload: Annotated[TokenData, Depends(require_teacher)],
    student_svc: StudentService = Depends(StudentService),
) -> JSONResponse:
    seconds = await student_svc.get_weekly_study_in_course(student_id, course_id, payload.id)
    return response_success({"daily_seconds": seconds})


@router.get("/tasks-todo", description="学生获取待办学习任务列表")
async def get_student_tasks_todo(
    payload: Annotated[TokenData, Depends(require_student)],
    student_svc: StudentService = Depends(StudentService),
) -> JSONResponse:
    data = await student_svc.get_tasks_todo(payload.id)
    return response_success(data)
