import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from typing import Annotated
from app.core.security import require_student, require_teacher
from app.crud.db import db_get_student_weekly_study, db_get_student_tasks_todo, db_get_student_weekly_study_in_course
from app.model.schema.schema import TokenData
from app.core.response import _success, _error

router = APIRouter()


def _handle_db_exception(e: Exception) -> JSONResponse | None:
    """
    函数目的：将 DB 层抛出的异常按规范分流，401/403 抛原生 HTTP 错误，404/400/409 转标准 JSON 信封。
    参数信息：
        - e: Exception，捕获到的异常实例。
    返回值信息：
        - JSONResponse | None：可序列化的错误响应，非业务异常时返回 None 交由全局处理器。
    """
    from fastapi import HTTPException, status
    if isinstance(e, HTTPException):
        if e.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
            raise e
        if e.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND, status.HTTP_409_CONFLICT):
            return _error(e.status_code, e.detail)
    return None


@router.get("/weekly-study", description="学生获取本周每日学习时长(秒)")
async def get_student_weekly_study(payload: Annotated[TokenData, Depends(require_student)]) -> JSONResponse:
    """
    函数目的：处理学生获取自己本周所有课程每日学习秒数的请求。
    参数信息：
        - payload: TokenData，依赖注入的当前登录学生Token载荷信息。
    返回值信息：
        - JSONResponse：包含 daily_seconds 数组（周一=索引0，周日=索引6）的统一响应信封。
    """
    try:
        seconds = await db_get_student_weekly_study(payload.id)
        return _success({"daily_seconds": seconds})
    except Exception as e:
        err_resp = _handle_db_exception(e)
        if err_resp:
            return err_resp
        raise


@router.get("/{student_id}/course/{course_id}/weekly-study", description="教师获取指定学生在某课程的本周每日学习时长(秒)")
async def get_student_weekly_study_by_teacher(
    student_id: str,
    course_id: uuid.UUID,
    payload: Annotated[TokenData, Depends(require_teacher)]
) -> JSONResponse:
    """
    函数目的：处理教师获取指定学生在某特定课程的本周每日学习秒数的请求。
    参数信息：
        - student_id: str，路径参数，目标学生的ID。
        - course_id: uuid.UUID，路径参数，目标课程的UUID。
        - payload: TokenData，依赖注入的当前登录教师Token载荷信息，用于后端越权校验。
    返回值信息：
        - JSONResponse：包含 daily_seconds 数组（周一=索引0，周日=索引6）的统一响应信封。
    """
    try:
        seconds = await db_get_student_weekly_study_in_course(student_id, course_id, payload.id)
        return _success({"daily_seconds": seconds})
    except Exception as e:
        err_resp = _handle_db_exception(e)
        if err_resp:
            return err_resp
        raise


@router.get("/tasks-todo", description="学生获取待办学习任务列表")
async def get_student_tasks_todo(payload: Annotated[TokenData, Depends(require_student)]) -> JSONResponse:
    """
    函数目的：处理学生获取自己所有待办学习任务（普通测验和GAI对话分析任务）列表的请求。
    参数信息：
        - payload: TokenData，依赖注入的当前登录学生Token载荷信息。
    返回值信息：
        - JSONResponse：包含 tasks 和 gai_tasks 列表的统一响应信封。
    """
    try:
        data = await db_get_student_tasks_todo(payload.id)
        return _success(data)
    except Exception as e:
        err_resp = _handle_db_exception(e)
        if err_resp:
            return err_resp
        raise
