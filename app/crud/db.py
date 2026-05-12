""" 数据库相关的操作函数 (asyncpg) """
from typing import Union
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlmodel import select, delete
from sqlalchemy import func, or_

from app.core.formatters import (
    _format_utc_time,
    _validate_task_payload_consistency,
    _normalize_chat_history,
)
# 物理文件操作工具
from app.core.tools import remove_file, _to_upload_relative_path, _is_deletable_resource_path
# 引擎与会话工厂由 core.database 统一管理
from app.core.database import engine, async_session_factory

from app.model.tables.models import *
from app.model.schema.course import CourseInfo, ChapterBatchPayload, CourseDetailRead, CourseRead
from app.model.schema.schema import RoleType, UserInDB, UserPublish
from app.model.schema.classes import ClassRead


# 纯业务异常定义
class AppBusinessException(Exception):
    """业务阻断异常：仅用于表达业务规则拒绝(404/403/400)。严禁用于表达系统故障。"""
    def __init__(self, code: int, message: str, log_module: str = "db"):
        self.code = code
        self.message = message
        self.log_module = log_module


#  初始化数据 
async def init_mock_data():
    """ 函数目的：初始化系统的测试基础数据（包含必填学段）。
    """
    from app.core.security import get_password_hash

    await db_insert_new_admin(
        UserInDB(id="Admin", role=RoleType.admin, username="Default_value", hashed_password=get_password_hash("Default_value")))


async def create_bd_and_table():
    """ 异步创建表 """
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    await init_mock_data()


#  基础用户与组织架构 
async def db_get_user_info(id: str, role: RoleType) -> Union[dict, None]:
    """函数目的：获取用户基础信息及所属机构的必填学段信息，用于鉴权和JWT签发。
    参数信息：- id: str, 用户ID; - role: RoleType, 用户角色。
    返回值：包含用户信息及 phase 的字典，不存在返回 None。
    """
    async with async_session_factory() as session:
        if role == RoleType.student:
            statement = select(Student).where(Student.id == id)
        elif role == RoleType.teacher:
            statement = select(Teacher).where(Teacher.id == id)
        else:
            statement = select(Admin).where(Admin.id == id)

        user = (await session.exec(statement)).one_or_none()
        if not user:
            return None

        base_info = {
            "id": user.id,
            "role": role,
            "username": user.username,
            "hashed_password": user.hashed_password,
            "student_class": "",
            "phase": PhaseType.senior
        }

        if role == RoleType.student:
            base_info.update({"class_id": user.class_id, "organization_id": user.organization_id})
            class_obj = await session.get(StudentClass, user.class_id)
            if class_obj:
                base_info["student_class"] = class_obj.class_name

            org_obj = await session.get(Organization, user.organization_id)
            if org_obj:
                base_info["phase"] = org_obj.phase

        elif role == RoleType.teacher:
            base_info.update({"organization_id": user.organization_id})
            org_obj = await session.get(Organization, user.organization_id)
            if org_obj:
                base_info["phase"] = org_obj.phase

        return base_info


async def db_create_new_organization(org_name: str, phase: PhaseType, prefix: str = "") -> int:
    """函数目的：创建新组织或返回已存在组织的ID。
    参数信息：- org_name: str, 组织名; - phase: PhaseType, 学段(必填); - prefix: str, 前缀。
    返回值：int, 组织ID。
    """
    async with async_session_factory() as session:
        statement = select(Organization).where(Organization.organization_name == org_name)
        is_org_exist = (await session.exec(statement)).one_or_none()
        if not is_org_exist:
            new_org = Organization(organization_name=org_name, phase=phase, prefix=prefix)
            session.add(new_org)
            await session.commit()
            await session.refresh(new_org)
            return new_org.organization_id
        return is_org_exist.organization_id


async def db_get_organization_id_by_name(organization_name: str) -> int:
    async with async_session_factory() as session:
        statement = select(Organization).where(Organization.organization_name == organization_name)
        org = (await session.exec(statement)).one_or_none()
        if not org:
            raise AppBusinessException(400, "该组织不存在，学生无法加入")
        return org.organization_id


async def db_get_class_id_in_organization(class_name: str, organization_id: int) -> int:
    async with async_session_factory() as session:
        statement = select(StudentClass).where(StudentClass.class_name == class_name,
                                               StudentClass.organization_id == organization_id)
        db_class = (await session.exec(statement)).one_or_none()
        if not db_class:
            raise AppBusinessException(400, "该组织下不存在此班级，学生无法加入")
        return db_class.class_id


async def db_create_new_class(class_name: str, organization_id: int) -> tuple[int, int]:
    async with async_session_factory() as session:
        statement = select(StudentClass).where(
            StudentClass.class_name == class_name,
            StudentClass.organization_id == organization_id
        )
        is_class_exist = (await session.exec(statement)).one_or_none()
        if not is_class_exist:
            new_class = StudentClass(class_name=class_name, organization_id=organization_id)
            session.add(new_class)
            await session.commit()
            await session.refresh(new_class)
            return (new_class.class_id, new_class.organization_id)
        return (is_class_exist.class_id, is_class_exist.organization_id)


async def db_insert_new_student(user: UserInDB) -> bool:
    async with async_session_factory() as session:
        statement = select(Student).where(Student.id == user.id)
        if (await session.exec(statement)).one_or_none():
            return False
        session.add(
            Student(id=user.id, username=user.username, class_id=user.class_id, organization_id=user.organization_id,
                    hashed_password=user.hashed_password))
        await session.commit()
        return True


async def db_insert_new_teacher(user: UserInDB) -> bool:
    async with async_session_factory() as session:
        if (await session.exec(select(Teacher).where(Teacher.id == user.id))).one_or_none():
            return False
        session.add(Teacher(id=user.id, username=user.username, hashed_password=user.hashed_password,
                            organization_id=user.organization_id))
        await session.commit()
        return True


async def db_insert_new_admin(user: UserInDB) -> bool:
    async with async_session_factory() as session:
        if (await session.exec(select(Admin).where(Admin.id == user.id))).one_or_none():
            return False
        session.add(Admin(id=user.id, username=user.username, hashed_password=user.hashed_password))
        await session.commit()
        return True


async def db_delete_student(student_id: str) -> bool:
    async with async_session_factory() as session:
        student = await session.get(Student, student_id)
        if not student:
            raise AppBusinessException(404, "学生不存在")
        await session.delete(student)
        await session.commit()
        return True


async def db_delete_teacher(teacher_id: str) -> bool:
    async with async_session_factory() as session:
        teacher = await session.get(Teacher, teacher_id)
        if not teacher:
            raise AppBusinessException(404, "教师不存在")

        course_ids = (await session.exec(select(Course.course_id).where(Course.teacher_id == teacher_id))).all()

        cover_paths, section_paths = await _collect_course_resource_paths(course_ids)

        await session.delete(teacher)
        await session.commit()

        cover_paths = {p for p in cover_paths if p and p != "covers/default.png"}
        for path in cover_paths:
            await remove_file(path)
        await _cleanup_orphaned_section_resources(section_paths)
        return True


async def db_delete_class(class_id: int) -> bool:
    async with async_session_factory() as session:
        db_class = await session.get(StudentClass, class_id)
        if not db_class:
            raise AppBusinessException(404, "班级不存在")
        await session.delete(db_class)
        await session.commit()
        return True


async def db_delete_organization(organization_id: int) -> bool:
    async with async_session_factory() as session:
        org = await session.get(Organization, organization_id)
        if not org:
            raise AppBusinessException(404, "组织不存在")

        teacher_ids = (await session.exec(select(Teacher.id).where(Teacher.organization_id == organization_id))).all()
        course_ids = (await session.exec(
            select(Course.course_id).where(Course.teacher_id.in_(teacher_ids)))).all() if teacher_ids else []

        cover_paths, section_paths = await _collect_course_resource_paths(course_ids)

        await session.delete(org)
        await session.commit()

        cover_paths = {p for p in cover_paths if p and p != "covers/default.png"}
        for path in cover_paths:
            await remove_file(path)
        await _cleanup_orphaned_section_resources(section_paths)

        return True


async def db_get_teacher_org_id(teacher_id: str) -> int | None:
    async with async_session_factory() as session:
        teacher = await session.get(Teacher, teacher_id)
        return teacher.organization_id if teacher else None


async def db_get_classes_by_organization(organization_id: int) -> list[dict]:
    async with async_session_factory() as session:
        classes = (
            await session.exec(select(StudentClass).where(StudentClass.organization_id == organization_id))).all()
        return [ClassRead.model_validate(c).model_dump(mode='json') for c in classes]


async def db_get_all_classes() -> list[dict]:
    async with async_session_factory() as session:
        return [ClassRead.model_validate(c).model_dump(mode='json') for c in
                (await session.exec(select(StudentClass))).all()]


async def db_update_user(user_info: UserPublish, hashed_password: str) -> bool:
    async with async_session_factory() as session:
        table_map = {RoleType.student: Student, RoleType.teacher: Teacher, RoleType.admin: Admin}
        user = await session.get(table_map[user_info.role], user_info.id)
        if not user:
            return False
        user.hashed_password = hashed_password
        session.add(user)
        await session.commit()
        return True


#  课程与章节核心逻辑 
async def db_get_courses_by_teacher_page(teacher_id: str, page: int, size: int = 16) -> list[dict]:
    offset = (page - 1) * size
    async with async_session_factory() as session:
        courses = (await session.exec(
            select(Course).where(Course.teacher_id == teacher_id).order_by(Course.course_id).offset(offset).limit(size)
        )).all()
        return [CourseRead.model_validate(c).model_dump(mode='json') for c in courses]


async def db_create_course_with_students(course_info: CourseInfo, class_names: list[str]) -> uuid.UUID:
    async with async_session_factory() as session:
        course = Course(course_name=course_info.course_name, teacher_id=course_info.teacher_id,
                        course_cover=course_info.course_cover, teaching_plan=course_info.teaching_plan,
                        invited_code=course_info.invited_code, is_invitation_valid=course_info.is_invitation_valid)
        session.add(course)
        await session.flush()

        if class_names:
            class_ids = (
                await session.exec(select(StudentClass.class_id).where(StudentClass.class_name.in_(class_names)))).all()
            if class_ids:
                student_ids = (await session.exec(select(Student.id).where(Student.class_id.in_(class_ids)))).all()
                if student_ids:
                    session.add_all(
                        [CourseRegistrationRecord(student_id=sid, course_id=course.course_id) for sid in student_ids])
                    await session.flush()
        await session.commit()
        return course.course_id


async def db_get_course_detail(course_id: uuid.UUID, teacher_id: str) -> dict:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course:
            raise AppBusinessException(404, "课程不存在")
        if course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权查看此课程")
        return CourseDetailRead.model_validate(course).model_dump(mode='json')


async def db_get_chapters_with_sections(course_id: uuid.UUID, student_id: str | None = None,
                                        teacher_id: str | None = None) -> list[dict]:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course:
            raise AppBusinessException(404, "课程不存在")
        if student_id:
            if not (await session.exec(
                    select(CourseRegistrationRecord).where(
                        CourseRegistrationRecord.student_id == student_id,
                        CourseRegistrationRecord.course_id == course_id
                    )
            )).first():
                raise AppBusinessException(403, "无权访问此课程")
        elif teacher_id and course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权访问此课程")

        statement = (
            select(Chapter)
            .where(Chapter.course_id == course_id)
            .options(selectinload(Chapter.sections))
            .order_by(Chapter.chapter_order)
        )
        chapters = (await session.exec(statement)).all()

        if not chapters:
            return []

        completions, learning_effects = set(), {}
        if student_id:
            all_section_ids = [s.section_id for ch in chapters for s in ch.sections]
            if all_section_ids:
                for rec in (await session.exec(
                        select(SectionCompletionRecord).where(
                            SectionCompletionRecord.student_id == student_id,
                            SectionCompletionRecord.section_id.in_(all_section_ids)
                        )
                )).all():
                    completions.add(rec.section_id)
                    learning_effects[rec.section_id] = rec.learning_effect

        result = []
        for ch in chapters:
            sub_tasks = []
            for s in sorted(ch.sections, key=lambda x: x.section_order):
                task_data = {
                    "section_id": s.section_id,
                    "section_title": s.section_title,
                    "section_type": s.section_type.value,
                    "resource_path": s.resource_path,
                    "description": s.description,
                    "section_order": s.section_order
                }
                if student_id is not None:
                    task_data["is_completed"] = s.section_id in completions
                    task_data["learning_effect"] = learning_effects.get(s.section_id, 0)
                sub_tasks.append(task_data)
            result.append({
                "chapter_id": ch.chapter_id,
                "chapter_title": ch.chapter_title,
                "chapter_order": ch.chapter_order,
                "sub_tasks": sub_tasks
            })
        return result


async def _cleanup_orphaned_section_resources(candidate_paths: set[str]) -> None:
    if not candidate_paths: return
    safe_paths = {p for p in candidate_paths if p and _is_deletable_resource_path(p)}
    if not safe_paths: return
    async with async_session_factory() as session:
        referenced = set(
            (await session.exec(select(Section.resource_path).where(Section.resource_path.in_(safe_paths)))).all())
        for path in safe_paths - referenced:
            await remove_file(_to_upload_relative_path(path))


async def _collect_course_resource_paths(course_ids: list[uuid.UUID]) -> tuple[set[str], set[str]]:
    if not course_ids: return set(), set()
    async with async_session_factory() as session:
        return (
            set((await session.exec(select(Course.course_cover).where(Course.course_id.in_(course_ids)))).all()),
            set((await session.exec(
                select(Section.resource_path).join(Chapter, Section.chapter_id == Chapter.chapter_id).where(
                    Chapter.course_id.in_(course_ids)))).all())
        )


async def db_delete_course(teacher_id: str, course_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course:
            raise AppBusinessException(404, "课程不存在")
        if course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权删除此课程")
        cover_to_remove = course.course_cover if course.course_cover and course.course_cover != "covers/default.png" else None
        section_paths = (await session.exec(
            select(Section.resource_path).join(Chapter, Section.chapter_id == Chapter.chapter_id).where(
                Chapter.course_id == course_id))).all()
        await session.delete(course)
        await session.commit()
        if cover_to_remove:
            await remove_file(cover_to_remove)
        await _cleanup_orphaned_section_resources(set(section_paths))


async def db_batch_update_chapters(course_id: uuid.UUID, payload: ChapterBatchPayload, teacher_id: str) -> list[dict]:
    removed_resource_paths: set[str] = set()
    try:
        async with async_session_factory() as session:
            course = await session.get(Course, course_id)
            if not course:
                raise AppBusinessException(404, "课程不存在")
            if course.teacher_id != teacher_id:
                raise AppBusinessException(403, "无权修改此课程")

            req_chapter_ids = {ch.chapter_id for ch in payload.chapters if ch.chapter_id is not None}
            db_chapters = (await session.exec(select(Chapter).where(Chapter.course_id == course_id))).all()
            to_delete_ch_ids = [ch.chapter_id for ch in db_chapters if ch.chapter_id not in req_chapter_ids]

            if to_delete_ch_ids:
                removed_paths = (await session.exec(
                    select(Section.resource_path).where(Section.chapter_id.in_(to_delete_ch_ids))
                )).all()
                removed_resource_paths.update({p for p in removed_paths if p})
                await session.execute(delete(Chapter).where(Chapter.chapter_id.in_(to_delete_ch_ids)))

            temp_order = -1
            for ch in (await session.exec(select(Chapter).where(Chapter.course_id == course_id))).all():
                ch.chapter_order = temp_order
                temp_order -= 1
            await session.flush()

            new_chapter_objs = []
            for ch_data in payload.chapters:
                current_real_ch_id = ch_data.chapter_id
                if ch_data.chapter_id is None:
                    new_ch = Chapter(course_id=course_id, chapter_title=ch_data.chapter_title, chapter_order=temp_order)
                    session.add(new_ch)
                    await session.flush()
                    current_real_ch_id = new_ch.chapter_id
                    new_chapter_objs.append((ch_data, new_ch))
                    temp_order -= 1
                else:
                    db_ch = await session.get(Chapter, current_real_ch_id)
                    if not db_ch:
                        raise AppBusinessException(404, "章节不存在")
                    if db_ch.course_id != course_id:
                        raise AppBusinessException(403, "无权修改此章节")
                    db_ch.chapter_title = ch_data.chapter_title

                req_sec_ids = {s.section_id for s in ch_data.sub_tasks if s.section_id is not None}
                db_secs = (await session.exec(select(Section).where(Section.chapter_id == current_real_ch_id))).all()
                del_sec_ids = [s.section_id for s in db_secs if s.section_id not in req_sec_ids]

                if del_sec_ids:
                    removed_paths = (await session.exec(
                        select(Section.resource_path).where(Section.section_id.in_(del_sec_ids))
                    )).all()
                    removed_resource_paths.update({p for p in removed_paths if p})
                    await session.execute(delete(Section).where(Section.section_id.in_(del_sec_ids)))

                temp_sec_order = -1
                for sec in (await session.exec(select(Section).where(Section.chapter_id == current_real_ch_id))).all():
                    sec.section_order = temp_sec_order
                    temp_sec_order -= 1
                await session.flush()

                section_objs = []
                for st_data in ch_data.sub_tasks:
                    if st_data.section_id is None:
                        if not st_data.resource_path:
                            raise AppBusinessException(400, "子任务资源不能为空，请先上传资源文件")
                        new_sec = Section(
                            section_title=st_data.section_title,
                            section_type=st_data.section_type,
                            resource_path=st_data.resource_path,
                            description=st_data.description,
                            chapter_id=current_real_ch_id,
                            section_order=temp_sec_order
                        )
                        session.add(new_sec)
                        await session.flush()
                        section_objs.append(new_sec)
                        temp_sec_order -= 1
                    else:
                        db_sec = await session.get(Section, st_data.section_id)
                        if not db_sec:
                            raise AppBusinessException(404, "子任务不存在")
                        if db_sec.chapter_id != current_real_ch_id:
                            raise AppBusinessException(403, "无权修改此子任务")
                        if not st_data.resource_path:
                            raise AppBusinessException(400, "子任务资源不能为空，请先上传资源文件")
                        if db_sec.resource_path and db_sec.resource_path != st_data.resource_path:
                            removed_resource_paths.add(db_sec.resource_path)
                        db_sec.section_title = st_data.section_title
                        db_sec.section_type = st_data.section_type
                        db_sec.resource_path = st_data.resource_path
                        db_sec.description = st_data.description
                        section_objs.append(db_sec)

                for idx, sec_obj in enumerate(section_objs):
                    sec_obj.section_order = idx + 1

            for idx, ch_data in enumerate(payload.chapters):
                target_id = ch_data.chapter_id
                if target_id is None:
                    for p_data, ch_obj in new_chapter_objs:
                        if p_data is ch_data:
                            target_id = ch_obj.chapter_id
                            break
                if target_id:
                    db_ch = await session.get(Chapter, target_id)
                    db_ch.chapter_order = ch_data.chapter_order if ch_data.chapter_order is not None else idx + 1

            await session.commit()

            final_chapters = (await session.exec(
                select(Chapter).where(Chapter.course_id == course_id).order_by(Chapter.chapter_order)
            )).all()

            result = []
            for ch in final_chapters:
                secs = (await session.exec(
                    select(Section).where(Section.chapter_id == ch.chapter_id).order_by(Section.section_order)
                )).all()
                result.append({
                    "chapter_id": ch.chapter_id,
                    "chapter_title": ch.chapter_title,
                    "chapter_order": ch.chapter_order,
                    "sub_tasks": [{
                        "section_id": s.section_id,
                        "section_title": s.section_title,
                        "section_type": s.section_type.value,
                        "resource_path": s.resource_path,
                        "description": s.description,
                        "section_order": s.section_order
                    } for s in secs]
                })

            await _cleanup_orphaned_section_resources(removed_resource_paths)
            return result
    except AppBusinessException:
        raise
    except IntegrityError:
        raise AppBusinessException(400, "章节或子任务顺序冲突，请刷新后重试")


async def db_patch_course(course_id: uuid.UUID, teacher_id: str, update_data: dict) -> dict:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course: raise AppBusinessException(404, "课程不存在")
        if course.teacher_id != teacher_id: raise AppBusinessException(403, "无权修改此课程")
        valid_updates = {k: v for k, v in update_data.items() if v is not None}
        for key, value in valid_updates.items():
            if hasattr(course, key): setattr(course, key, value)
        session.add(course);
        await session.commit();
        await session.refresh(course)
        return {"course_id": str(course.course_id), "course_name": course.course_name,
                "course_cover": course.course_cover, "teaching_plan": course.teaching_plan,
                "invited_code": course.invited_code, "is_invitation_valid": course.is_invitation_valid}


async def db_join_course_by_code(student_id: str, invite_code: str) -> str:
    async with async_session_factory() as session:
        course = (await session.exec(select(Course).where(Course.invited_code == invite_code))).one_or_none()
        if not course: raise AppBusinessException(404, "课程不存在或邀请码错误")
        if not course.is_invitation_valid: raise AppBusinessException(400, "该课程的邀请码已失效")
        if (await session.exec(select(CourseRegistrationRecord).where(CourseRegistrationRecord.student_id == student_id,
                                                                      CourseRegistrationRecord.course_id == course.course_id))).first():
            raise AppBusinessException(400, "你已经加入了该课程")
        session.add(CourseRegistrationRecord(student_id=student_id, course_id=course.course_id))
        await session.commit()
        return str(course.course_id)


#  任务 (测验 & GAI) 核心逻辑 
async def db_create_task(course_id: uuid.UUID, teacher_id: str, task_data: dict) -> dict:
    """
    函数目的：创建测验任务，强校验后原样持久化 JSON。
    参数信息：
        - course_id: uuid.UUID，课程UUID。
        - teacher_id: str，教师ID。
        - task_data: dict，经由 TaskCreateAndUpdate.model_dump() 生成的纯字典。
    返回值：dict，包含 task_id 等基础信息的字典。
    """
    quiz_data = task_data.get("quiz", [])
    answer_data = task_data.get("answer", [])

    _validate_task_payload_consistency(quiz_data, answer_data)

    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权操作此课程")

        new_task = Task(
            course_id=course_id,
            task_title=task_data["task_title"],
            quiz=quiz_data,
            answer=answer_data,
            deadline=task_data.get("deadline")
        )
        session.add(new_task)
        await session.commit()
        await session.refresh(new_task)

        return {
            "task_id": new_task.task_id,
            "task_title": new_task.task_title,
            "type": "quiz",
            "quiz": new_task.quiz,
            "answer": new_task.answer,
            "deadline": _format_utc_time(new_task.deadline)
        }


async def db_update_task(course_id: uuid.UUID, task_id: int, teacher_id: str, task_data: dict) -> dict:
    """
    函数目的：更新测验任务，强校验后原样覆盖持久化 JSON。
    参数信息：同 db_create_task，增加 task_id。
    返回值：dict，更新后的任务信息字典。
    """
    quiz_data = task_data.get("quiz", [])
    answer_data = task_data.get("answer", [])

    _validate_task_payload_consistency(quiz_data, answer_data)

    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")
        course = await session.get(Course, course_id)
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权操作此课程")

        task.task_title = task_data["task_title"]
        task.quiz = quiz_data
        task.answer = answer_data
        task.deadline = task_data.get("deadline")

        session.add(task)
        await session.commit()
        await session.refresh(task)

        return {
            "task_id": task.task_id,
            "task_title": task.task_title,
            "type": "quiz",
            "quiz": task.quiz,
            "answer": task.answer,
            "deadline": _format_utc_time(task.deadline)
        }


async def db_get_task_detail_for_student(course_id: uuid.UUID, task_id: int, student_id: str | None) -> dict:
    """
    函数目的：学生获取任务详情，直接返回原始结构，废弃下标推导。
    参数信息：
        - course_id: uuid.UUID，课程UUID。
        - task_id: int，任务ID。
        - student_id: str | None，学生ID。
    返回值：dict，包含题目、学生作答状态及历史记录的字典。
    """
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")
        if student_id:
            if not (await session.exec(select(CourseRegistrationRecord.registration_id).where(
                    CourseRegistrationRecord.student_id == student_id,
                    CourseRegistrationRecord.course_id == course_id))).first():
                raise AppBusinessException(403, "无权访问此课程")

        quiz_items = task.quiz or []
        response = {
            "task_title": task.task_title,
            "deadline": _format_utc_time(task.deadline),
            "quiz": quiz_items,
            "is_completed": False
        }

        if student_id:
            completion = (await session.exec(select(TaskCompletion).where(
                TaskCompletion.task_id == task_id,
                TaskCompletion.student_id == student_id
            ))).one_or_none()

            if completion:
                response.update({
                    "is_completed": True,
                    "student_answers": completion.answer,
                    "task_scores": completion.task_scores,
                    "task_analysis": completion.task_analysis
                })
        return response


async def db_get_task_detail_for_edit(course_id: uuid.UUID, task_id: int, teacher_id: str) -> dict:
    """
    函数目的：教师获取任务编辑详情，严格按接口文档原样返回，供前端回显。
    参数信息：
        - course_id: uuid.UUID，课程UUID。
        - task_id: int，任务ID。
        - teacher_id: str，教师ID。
    返回值：dict，完全符合请求载荷格式的数据字典。
    """
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")
        course = await session.get(Course, course_id)
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权操作此课程")

        return {
            "task_title": task.task_title,
            "deadline": _format_utc_time(task.deadline),
            "quiz": task.quiz if task.quiz else [],
            "answer": task.answer if task.answer else []
        }


async def db_get_task_review_data(course_id: uuid.UUID, task_id: int, student_id: str) -> dict:
    """
    函数目的：学生获取批改回顾，通过 question_id 构建映射进行精准关联，废弃下标对齐。
    参数信息：
        - course_id: uuid.UUID，课程UUID。
        - task_id: int，任务ID。
        - student_id: str，学生ID。
    返回值：dict，包含分数、分析及逐题对照的字典。
    """
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course:
            raise AppBusinessException(404, "课程不存在")
        if not (await session.exec(select(CourseRegistrationRecord.registration_id).where(
                CourseRegistrationRecord.student_id == student_id,
                CourseRegistrationRecord.course_id == course_id))).first():
            raise AppBusinessException(403, "无权访问此课程")
        task = await session.get(Task, task_id)
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")
        completion = (await session.exec(select(TaskCompletion).where(
            TaskCompletion.task_id == task_id,
            TaskCompletion.student_id == student_id
        ))).one_or_none()
        if not completion:
            raise AppBusinessException(404, "任务未提交，无法查看回顾")

        quiz_items = task.quiz or []
        answer_items = task.answer or []
        student_answers = completion.answer or []

        correct_answer_map = {item.get("question_id"): item.get("correct_answer") for item in answer_items if
                              isinstance(item, dict)}
        std_answer_map = {item.get("question_id"): item.get("answer") for item in student_answers if
                          isinstance(item, dict)}

        questions_review = []
        for q_item in quiz_items:
            if not isinstance(q_item, dict): continue
            q_id = q_item.get("question_id")

            questions_review.append({
                "question_id": q_id,
                "student_answer": std_answer_map.get(q_id),
                "correct_answer": correct_answer_map.get(q_id)
            })

        return {
            "task_score": completion.task_scores,
            "ai_analysis": completion.task_analysis if completion.task_analysis else "",
            "questions": questions_review
        }


async def db_get_task_raw_for_grading(completion_id: int) -> dict | None:
    """
    函数目的：为后台打分任务获取纯净的原始数据结构。
    参数信息：- completion_id: int，提交记录ID。
    返回值：包含 quiz, answer, student_answer 的原样字典。
    """
    async with async_session_factory() as session:
        record = await session.get(TaskCompletion, completion_id)
        if not record:
            return None
        task = await session.get(Task, record.task_id)
        if not task:
            return None
        return {
            "quiz": task.quiz or [],
            "answer": task.answer or [],
            "student_answer": record.answer or []
        }


async def db_update_task_grading_result(completion_id: int, final_score: float, analysis_text: str) -> None:
    """函数目的：后台任务更新最终得分和分析状态文本。
    参数信息：
        - completion_id: int，提交记录表的主键 ID。
        - final_score: float，最终得分（可以是小数如 75.5）。
        - analysis_text: str，分析状态文本（成功为"评分完成"，失败为错误提示）。
    返回值：无。
    """
    async with async_session_factory() as session:
        record = await session.get(TaskCompletion, completion_id)
        if record:
            record.task_scores = int(final_score) if final_score == int(final_score) else final_score
            record.task_analysis = analysis_text
            session.add(record)
            await session.commit()


async def db_delete_task(course_id: uuid.UUID, task_id: int, teacher_id: str) -> None:
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        if not task or task.course_id != course_id: raise AppBusinessException(404, "任务不存在")
        course = await session.get(Course, course_id)
        if not course or course.teacher_id != teacher_id: raise AppBusinessException(403, "无权操作此课程")
        await session.delete(task);
        await session.commit()


async def db_create_gai_task(course_id: uuid.UUID, teacher_id: str, task_data: dict) -> dict:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course or course.teacher_id != teacher_id: raise AppBusinessException(403, "无权操作此课程")
        new_task = AnalysisTask(course_id=course_id, **task_data)
        session.add(new_task);
        await session.commit();
        await session.refresh(new_task)
        return {"analysis_task_id": new_task.analysis_task_id, "analysis_task_title": new_task.analysis_task_title,
                "task_description": new_task.task_description, "analysis_description": new_task.analysis_description,
                "evaluation_criterion": new_task.evaluation_criterion, "deadline": _format_utc_time(new_task.deadline)}


async def db_update_gai_task(course_id: uuid.UUID, task_id: int, teacher_id: str, task_data: dict) -> dict:
    async with async_session_factory() as session:
        task = await session.get(AnalysisTask, task_id)
        if not task or task.course_id != course_id: raise AppBusinessException(404, "任务不存在")
        course = await session.get(Course, course_id)
        if not course or course.teacher_id != teacher_id: raise AppBusinessException(403, "无权操作此课程")
        for key, value in task_data.items(): setattr(task, key, value)
        session.add(task);
        await session.commit();
        await session.refresh(task)
        return {"analysis_task_id": task.analysis_task_id, "analysis_task_title": task.analysis_task_title,
                "task_description": task.task_description, "analysis_description": task.analysis_description,
                "evaluation_criterion": task.evaluation_criterion, "deadline": _format_utc_time(task.deadline)}


async def db_delete_gai_task(course_id: uuid.UUID, task_id: int, teacher_id: str) -> None:
    async with async_session_factory() as session:
        task = await session.get(AnalysisTask, task_id)
        if not task or task.course_id != course_id: raise AppBusinessException(404, "任务不存在")
        course = await session.get(Course, course_id)
        if not course or course.teacher_id != teacher_id: raise AppBusinessException(403, "无权操作此课程")
        await session.delete(task);
        await session.commit()


async def db_get_tasks_by_course(course_id: uuid.UUID, user_id: str, role: str) -> list[dict]:
    """函数目的：获取指定课程下全部测验任务摘要列表，学生端额外附带完成状态。
    参数信息：
        - course_id: uuid.UUID，目标课程 UUID。
        - user_id: str，当前请求用户 ID。
        - role: str，用户角色（"student" 或 "teacher"）。
    返回值：list[dict]，任务摘要字典列表；学生端每项包含 is_completed 布尔值，教师端不包含。
    """
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course:
            raise AppBusinessException(404, "课程不存在")
        if role == "teacher" and course.teacher_id != user_id:
            raise AppBusinessException(403, "无权查看此课程")
        elif role == "student" and not (await session.exec(
                select(CourseRegistrationRecord).where(
                    CourseRegistrationRecord.student_id == user_id,
                    CourseRegistrationRecord.course_id == course_id
                ))).first():
            raise AppBusinessException(403, "无权访问此课程")

        tasks = (await session.exec(
            select(Task).where(Task.course_id == course_id).order_by(Task.task_id.desc())
        )).all()

        # 批量预加载学生完成状态，避免 N+1 查询
        completed_task_ids: set[int] = set()
        if role == "student" and tasks:
            task_ids = [t.task_id for t in tasks]
            completed_task_ids = set(
                (await session.exec(
                    select(TaskCompletion.task_id).where(
                        TaskCompletion.task_id.in_(task_ids),
                        TaskCompletion.student_id == user_id
                    )
                )).all()
            )

        result: list[dict] = []
        for t in tasks:
            item: dict = {
                "task_id": t.task_id,
                "task_title": t.task_title,
                "deadline": _format_utc_time(t.deadline),
            }
            if role == "student":
                item["is_completed"] = t.task_id in completed_task_ids
            result.append(item)
        return result


async def db_get_gai_tasks_by_course(course_id: uuid.UUID, user_id: str, role: str) -> list[dict]:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course: raise AppBusinessException(404, "课程不存在")
        if role == "teacher" and course.teacher_id != user_id: raise AppBusinessException(403, "无权查看此课程")
        result = []
        for t in (await session.exec(select(AnalysisTask).where(AnalysisTask.course_id == course_id).order_by(
                AnalysisTask.analysis_task_id.desc()))).all():
            task_data = {"analysis_task_id": t.analysis_task_id, "analysis_task_title": t.analysis_task_title,
                         "task_description": t.task_description, "analysis_description": t.analysis_description,
                         "evaluation_criterion": t.evaluation_criterion, "deadline": _format_utc_time(t.deadline),
                         "is_completed": False}
            if role == "student":
                task_data["is_completed"] = (await session.exec(
                    select(AnalysisTaskCompletion).where(AnalysisTaskCompletion.analysis_task_id == t.analysis_task_id,
                                                         AnalysisTaskCompletion.student_id == user_id))).first() is not None
            result.append(task_data)
        return result


#  学生学习与提交逻辑 
async def db_student_complete_section(course_id: uuid.UUID, section_id: int, student_id: str) -> None:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course: raise AppBusinessException(404, "课程不存在")
        if not (await session.exec(
                select(CourseRegistrationRecord.registration_id).where(
                    CourseRegistrationRecord.student_id == student_id,
                    CourseRegistrationRecord.course_id == course_id))).first(): raise AppBusinessException(
            403, "无权访问此课程")
        if not (await session.exec(
                select(Section.section_id).join(Chapter, Section.chapter_id == Chapter.chapter_id).where(
                    Section.section_id == section_id,
                    Chapter.course_id == course_id))).first(): raise AppBusinessException(
            404, "小节不存在")
        if (await session.exec(select(SectionCompletionRecord).where(SectionCompletionRecord.section_id == section_id,
                                                                     SectionCompletionRecord.student_id == student_id))).one_or_none(): return
        session.add(SectionCompletionRecord(section_id=section_id, student_id=student_id, learning_effect=0))
        await session.commit()


async def db_student_feedback_section(course_id: uuid.UUID, section_id: int, student_id: str, difficulty: int) -> None:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course: raise AppBusinessException(404, "课程不存在")
        if not (await session.exec(
                select(CourseRegistrationRecord.registration_id).where(
                    CourseRegistrationRecord.student_id == student_id,
                    CourseRegistrationRecord.course_id == course_id))).first(): raise AppBusinessException(
            403, "无权访问此课程")
        if not (await session.exec(
                select(Section.section_id).join(Chapter, Section.chapter_id == Chapter.chapter_id).where(
                    Section.section_id == section_id,
                    Chapter.course_id == course_id))).first(): raise AppBusinessException(
            404, "小节不存在")
        record = (await session.exec(
            select(SectionCompletionRecord).where(SectionCompletionRecord.section_id == section_id,
                                                  SectionCompletionRecord.student_id == student_id))).one_or_none()
        if record and record.learning_effect and record.learning_effect > 0: raise AppBusinessException(400,
                                                                                                        "反馈已提交")
        if record:
            record.learning_effect = difficulty;
            session.add(record)
        else:
            session.add(
                SectionCompletionRecord(section_id=section_id, student_id=student_id, learning_effect=difficulty))
        await session.commit()


async def db_submit_task_answer_for_grading(course_id: uuid.UUID, task_id: int, student_id: str, answers: list) -> int:
    """函数目的：学生提交答案，仅做业务校验与落库，不计算分数，状态设为 grading。
    参数信息：同原提交函数。
    返回值：int，新插入记录的主键 ID。
    """
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")
        if not (await session.exec(
                select(CourseRegistrationRecord.registration_id).where(
                    CourseRegistrationRecord.student_id == student_id,
                    CourseRegistrationRecord.course_id == course_id
                ))).first():
            raise AppBusinessException(403, "无权访问此课程")
        if (await session.exec(select(TaskCompletion).where(TaskCompletion.task_id == task_id,
                                                            TaskCompletion.student_id == student_id))).one_or_none():
            raise AppBusinessException(400, "已提交过答案")
        if task.deadline and datetime.now(UTC) > task.deadline:
            raise AppBusinessException(400, "任务已过截止时间，无法提交")

        completion_record = TaskCompletion(
            task_id=task_id,
            student_id=student_id,
            answer=answers,
            task_scores=0,
            task_analysis="grading"
        )
        session.add(completion_record)
        await session.flush()

        if completion_record.completion_id is None:
            raise AppBusinessException(500, "系统异常：提交记录主键生成失败")

        await session.commit()
        return completion_record.completion_id


# async def db_chat_gai_task(course_id: uuid.UUID, task_id: int, student_id: str, messages: list) -> str:
#     async with async_session_factory() as session:
#         task = await session.get(AnalysisTask, task_id)
#         if not task or task.course_id != course_id: raise AppBusinessException(404, "任务不存在")
#         if not (await session.exec(
#                 select(CourseRegistrationRecord.registration_id).where(
#                     CourseRegistrationRecord.student_id == student_id,
#                     CourseRegistrationRecord.course_id == course_id))).first(): raise AppBusinessException(
#             403, "无权访问此课程")
#         return str(uuid.uuid4())


async def db_submit_gai_task(course_id: uuid.UUID, task_id: int, student_id: str, messages: list) -> int:
    """函数目的：学生提交 GAI 任务对话，插入初始记录。
    参数信息：
    - course_id: uuid.UUID，课程UUID。
    - task_id: int，GAI任务ID。
    - student_id: str，学生ID。
    - messages: list，对话历史列表。
    返回值：int，新插入的提交记录的主键 ID，供后台任务追踪使用。
    """
    async with async_session_factory() as session:
        task = await session.get(AnalysisTask, task_id)
        if not task or task.course_id != course_id: raise AppBusinessException(404, "任务不存在")
        if not (await session.exec(
                select(CourseRegistrationRecord.registration_id).where(
                    CourseRegistrationRecord.student_id == student_id,
                    CourseRegistrationRecord.course_id == course_id))).first(): raise AppBusinessException(
            403, "无权访问此课程")
        if (await session.exec(select(AnalysisTaskCompletion).where(AnalysisTaskCompletion.analysis_task_id == task_id,
                                                                    AnalysisTaskCompletion.student_id == student_id))).one_or_none(): raise AppBusinessException(
            400, "已提交过任务")
        if task.deadline and datetime.now(UTC) > task.deadline: raise AppBusinessException(400,
                                                                                           "任务已过截止时间，无法提交")
        completion_record = AnalysisTaskCompletion(
            analysis_task_id=task_id,
            student_id=student_id,
            messages={"messages": messages},
            analysis_result="AI正在分析中",
            course_id=course_id
        )
        session.add(completion_record)
        await session.flush()
        completion_id = completion_record.completion_id
        await session.commit()
        return completion_id


async def db_get_analysis_task_info(task_id: int) -> dict | None:
    """函数目的：获取 GAI 任务的基础配置信息（供后台分析任务使用，独立会话）。
    参数信息：
    - task_id: int，GAI任务的ID。
    返回值：dict | None，包含任务描述、分析要求、评价标准的字典，不存在则返回 None。
    """
    async with async_session_factory() as session:
        task = await session.get(AnalysisTask, task_id)
        if not task:
            return None
        return {
            "task_description": task.task_description or "",
            "analysis_description": task.analysis_description or "",
            "evaluation_criterion": task.evaluation_criterion or "",
        }


async def db_update_gai_task_analysis_result(completion_id: int, result_text: str) -> None:
    """函数目的：根据提交记录 ID 更新最终的 AI 分析结果（供后台分析任务使用，独立会话）。
    参数信息：
    - completion_id: int，提交记录表的主键 ID。
    - result_text: str，最终要写入的分析文本（成功或失败的提示）。
    返回值：无。
    """
    async with async_session_factory() as session:
        record = await session.get(AnalysisTaskCompletion, completion_id)
        if record:
            record.analysis_result = result_text
            session.add(record)
            await session.commit()


#  教师数据看板与分析拉取逻辑 
async def db_get_course_students(course_id: uuid.UUID, teacher_id: str) -> list[dict]:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course or course.teacher_id != teacher_id: raise AppBusinessException(403, "无权查看此课程")
        return [{"id": s_id, "name": s_name} for s_id, s_name in (await session.exec(
            select(Student.id, Student.username).join(CourseRegistrationRecord,
                                                      Student.id == CourseRegistrationRecord.student_id).where(
                CourseRegistrationRecord.course_id == course_id).order_by(Student.id))).all()]


async def db_get_student_weekly_study_in_course(student_id: str, course_id: uuid.UUID, teacher_id: str) -> list[float]:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course or course.teacher_id != teacher_id: raise AppBusinessException(403, "无权查看此课程数据")
        records = (await session.exec(select(StudentDailyStudyTimeInCourse.study_data).where(
            StudentDailyStudyTimeInCourse.student_id == student_id,
            StudentDailyStudyTimeInCourse.course_id == course_id))).all()

        totals = [0] * 7
        for record in records:
            if not record:
                continue
            for idx in range(min(len(record), 7)):
                value = record[idx]
                totals[idx] += int(value) if value else 0
        return totals


async def db_get_completion_details(course_id: uuid.UUID, record_type: str, target_id: int, teacher_id: str) -> list[
    dict]:
    """
    函数目的：获取指定课程下，特定章节或测验任务的全班学生完成情况及得分明细。
    参数信息：
        - course_id: uuid.UUID，目标课程的唯一标识。
        - record_type: str，记录类型，只能为 "section"（章节）或 "task"（测验）。
        - target_id: int，目标资源的ID（对应 section_id 或 task_id）。
        - teacher_id: str，当前操作教师的ID，用于后端越权校验。
    返回值信息：
        - list[dict]: 包含学生姓名、是否完成、得分的字典列表。
    """
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权查看此课程")

        if record_type == "section":
            if not (await session.exec(
                    select(Section.section_id).join(Chapter).where(
                        Section.section_id == target_id,
                        Chapter.course_id == course_id
                    )
            )).first():
                raise AppBusinessException(404, "目标资源不存在")
        elif record_type == "task":
            if not (await session.exec(
                    select(Task.task_id).where(
                        Task.task_id == target_id,
                        Task.course_id == course_id
                    )
            )).first():
                raise AppBusinessException(404, "目标资源不存在")
        else:
            raise AppBusinessException(400, "type 参数错误")

        students = (await session.exec(
            select(Student.id, Student.username).join(CourseRegistrationRecord).where(
                CourseRegistrationRecord.course_id == course_id
            )
        )).all()
        student_map = {s_id: s_name for s_id, s_name in students}

        completion_map = {}
        if record_type == "section":
            records = (await session.exec(
                select(SectionCompletionRecord.student_id, SectionCompletionRecord.learning_effect).where(
                    SectionCompletionRecord.section_id == target_id
                )
            )).all()
            for s_id, effect in records:
                completion_map[s_id] = float(effect) if effect is not None else 0
        else:
            records = (await session.exec(
                select(TaskCompletion.student_id, TaskCompletion.task_scores).where(
                    TaskCompletion.task_id == target_id
                )
            )).all()
            for s_id, score in records:
                completion_map[s_id] = score if score is not None else 0

        return [
            {"student_name": s_name, "is_completed": s_id in completion_map, "score": completion_map.get(s_id, 0)}
            for s_id, s_name in student_map.items()
        ]


async def db_get_gai_task_students(course_id: uuid.UUID, task_id: int, teacher_id: str) -> list[dict]:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权查看此课程")
        task = await session.get(AnalysisTask, task_id)
        if not task or task.course_id != course_id:
            raise AppBusinessException(404, "任务不存在")
        students = (await session.exec(select(Student.id, Student.username).join(CourseRegistrationRecord).where(
            CourseRegistrationRecord.course_id == course_id))).all()
        if not students:
            return []
        completed_set = set(
            (await session.exec(
                select(AnalysisTaskCompletion.student_id).where(
                    AnalysisTaskCompletion.course_id == course_id,
                    AnalysisTaskCompletion.analysis_task_id == task_id,
                    AnalysisTaskCompletion.student_id.in_([s_id for s_id, _ in students])
                )
            )).all()
        )
        return [{"id": s_id, "name": s_name, "is_completed": s_id in completed_set} for s_id, s_name in students]


async def db_get_gai_task_student_analysis(course_id: uuid.UUID, task_id: int, teacher_id: str,
                                           student_id: str) -> dict:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course or course.teacher_id != teacher_id: raise AppBusinessException(403, "无权查看此课程")
        task = await session.get(AnalysisTask, task_id)
        if not task or task.course_id != course_id: raise AppBusinessException(404, "任务不存在")
        if not (await session.exec(
                select(CourseRegistrationRecord.registration_id).where(
                    CourseRegistrationRecord.student_id == student_id,
                    CourseRegistrationRecord.course_id == course_id))).first(): raise AppBusinessException(
            404, "学生不在该课程中")
        record = (await session.exec(select(AnalysisTaskCompletion).where(AnalysisTaskCompletion.course_id == course_id,
                                                                          AnalysisTaskCompletion.analysis_task_id == task_id,
                                                                          AnalysisTaskCompletion.student_id == student_id).order_by(
            AnalysisTaskCompletion.completion_id.desc()))).first()
        if not record: return {"chat_history": [], "analysis_text": ""}
        return {"chat_history": _normalize_chat_history(record.messages), "analysis_text": record.analysis_result or ""}


async def db_get_course_raw_records(course_id: uuid.UUID, teacher_id: str) -> list[dict]:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course or course.teacher_id != teacher_id: raise AppBusinessException(403, "无权查看此课程")
        student_ids = (await session.exec(
            select(CourseRegistrationRecord.student_id).where(CourseRegistrationRecord.course_id == course_id))).all()
        if not student_ids: return []
        records_map = {
            sid: {"student_id": sid, "done_section_ids": set(), "done_task_ids": set(), "done_gai_ids": set(),
                  "task_scores": {}} for sid in student_ids}
        section_ids = (await session.exec(
            select(Section.section_id).join(Chapter, Section.chapter_id == Chapter.chapter_id).where(
                Chapter.course_id == course_id))).all()
        task_ids = (await session.exec(select(Task.task_id).where(Task.course_id == course_id))).all()
        if section_ids:
            for sid, section_id in (await session.exec(
                    select(SectionCompletionRecord.student_id, SectionCompletionRecord.section_id).where(
                        SectionCompletionRecord.student_id.in_(student_ids),
                        SectionCompletionRecord.section_id.in_(section_ids)))).all():
                if sid in records_map: records_map[sid]["done_section_ids"].add(section_id)
        if task_ids:
            for sid, task_id, task_score in (await session.exec(
                    select(TaskCompletion.student_id, TaskCompletion.task_id, TaskCompletion.task_scores).where(
                        TaskCompletion.student_id.in_(student_ids), TaskCompletion.task_id.in_(task_ids)))).all():
                if sid in records_map: records_map[sid]["done_task_ids"].add(task_id); records_map[sid]["task_scores"][
                    str(task_id)] = task_score
        for sid, analysis_task_id in (await session.exec(
                select(AnalysisTaskCompletion.student_id, AnalysisTaskCompletion.analysis_task_id).where(
                    AnalysisTaskCompletion.course_id == course_id,
                    AnalysisTaskCompletion.student_id.in_(student_ids)))).all():
            if sid in records_map: records_map[sid]["done_gai_ids"].add(analysis_task_id)
        return [{"student_id": item["student_id"], "done_section_ids": sorted(item["done_section_ids"]),
                 "done_task_ids": sorted(item["done_task_ids"]), "done_gai_ids": sorted(item["done_gai_ids"]),
                 "task_scores": item["task_scores"]} for item in records_map.values()]


async def db_get_course_ai_text(course_id: uuid.UUID, teacher_id: str, student_id: str = "all") -> str:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course or course.teacher_id != teacher_id:
            raise AppBusinessException(403, "无权查看此课程")

        if student_id == "all":
            return course.teaching_analysis if course.teaching_analysis else "暂无全班综合 AI 分析数据。"

        is_registered = (await session.exec(
            select(CourseRegistrationRecord.registration_id).where(
                CourseRegistrationRecord.course_id == course_id,
                CourseRegistrationRecord.student_id == str(student_id)
            ))).first()
        if not is_registered:
            raise AppBusinessException(404, "学生不在该课程中")

        record = (await session.exec(
            select(AnalysisDescription.analysis_content).where(
                AnalysisDescription.course_id == course_id,
                AnalysisDescription.student_id == str(student_id)
            ).order_by(
                AnalysisDescription.analysis_id.desc()
            ))).first()
        return record if record else "暂无该学生的 AI 分析数据。"


#  学生视图辅助逻辑 
async def db_get_student_courses_page(student_id: str, page: int) -> dict:
    size = 16
    offset = (page - 1) * size
    async with async_session_factory() as session:
        results = (await session.exec(select(Course, Teacher.username).join(CourseRegistrationRecord,
                                                                            Course.course_id == CourseRegistrationRecord.course_id).join(
            Teacher, Course.teacher_id == Teacher.id).where(CourseRegistrationRecord.student_id == student_id).order_by(
            Course.course_id.desc()).offset(offset).limit(size + 1))).all()
        has_more = len(results) > size
        if has_more: results = results[:size]
        courses = []
        for course, teacher_name in results:
            course_id = str(course.course_id)
            courses.append({"course_id": course_id, "course_name": course.course_name, "teacher_name": teacher_name,
                            "course_cover": course.course_cover, "id": course_id, "name": course.course_name,
                            "teacher": teacher_name})
        return {"courses": courses, "has_more": has_more}


async def db_get_course_detail_for_student(course_id: uuid.UUID, student_id: str) -> dict:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course: raise AppBusinessException(404, "课程不存在")
        if not (await session.exec(
                select(CourseRegistrationRecord.registration_id).where(
                    CourseRegistrationRecord.student_id == student_id,
                    CourseRegistrationRecord.course_id == course_id))).first(): raise AppBusinessException(
            403, "无权访问此课程")
        teacher_name = (
            await session.exec(select(Teacher.username).where(Teacher.id == course.teacher_id))).one_or_none()
        return {"course_id": str(course.course_id), "course_name": course.course_name,
                "course_cover": course.course_cover, "teacher_name": teacher_name or ""}


async def db_get_section_detail(course_id: uuid.UUID, section_id: int, student_id: str) -> dict:
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course:
            raise AppBusinessException(404, "课程不存在")
        if not (await session.exec(
                select(CourseRegistrationRecord.registration_id).where(
                    CourseRegistrationRecord.student_id == student_id,
                    CourseRegistrationRecord.course_id == course_id
                )
        )).first():
            raise AppBusinessException(403, "无权访问此课程")

        record = (await session.exec(
            select(Section, Chapter.chapter_title).join(Chapter, Section.chapter_id == Chapter.chapter_id).where(
                Section.section_id == section_id,
                Chapter.course_id == course_id
            )
        )).one_or_none()

        if not record:
            raise AppBusinessException(404, "小节不存在")

        section, chapter_title = record
        completion = (await session.exec(
            select(SectionCompletionRecord.completion_id).where(
                SectionCompletionRecord.section_id == section_id,
                SectionCompletionRecord.student_id == student_id
            )
        )).first()

        return {
            "chapter_name": chapter_title,
            "section_title": section.section_title,
            "resource_type": section.section_type.value,
            "resource_url": section.resource_path,
            "description": section.description,
            "is_completed": completion is not None
        }


async def db_get_student_weekly_study(student_id: str) -> list[int]:
    """..."""
    async with async_session_factory() as session:
        records = (await session.exec(select(StudentDailyStudyTimeInCourse.study_data).where(
            StudentDailyStudyTimeInCourse.student_id == student_id))).all()

        totals = [0] * 7
        for record in records:
            if not record:
                continue
            for idx in range(min(len(record), 7)):
                value = record[idx]
                totals[idx] += int(value) if value else 0
        return totals


async def db_get_student_tasks_todo(student_id: str) -> dict:
    async with async_session_factory() as session:
        course_ids = (await session.exec(
            select(CourseRegistrationRecord.course_id).where(CourseRegistrationRecord.student_id == student_id))).all()
        if not course_ids: return {"tasks": [], "gai_tasks": []}
        current_time = datetime.now(UTC)
        completed_task_ids_set = set(
            (await session.exec(select(TaskCompletion.task_id).where(TaskCompletion.student_id == student_id))).all())
        todo_tasks = [
            {"task_id": str(task_id), "task_title": title, "course_name": course_name, "course_id": str(course_id),
             "is_completed": False, "deadline": _format_utc_time(deadline)} for
            task_id, title, course_name, course_id, deadline in (await session.exec(
                select(Task.task_id, Task.task_title, Course.course_name, Course.course_id, Task.deadline).join(Course,
                                                                                                                Task.course_id == Course.course_id).where(
                    Task.course_id.in_(course_ids),
                    (Task.deadline.is_(None)) | (Task.deadline >= current_time)).order_by(Task.task_id.desc()))).all()
            if task_id not in completed_task_ids_set]
        completed_gai_ids_set = set((await session.exec(select(AnalysisTaskCompletion.analysis_task_id).where(
            AnalysisTaskCompletion.student_id == student_id))).all())
        todo_gai_tasks = [
            {"task_id": str(task_id), "task_title": title, "course_name": course_name, "course_id": str(course_id),
             "is_completed": False, "deadline": _format_utc_time(deadline)} for
            task_id, title, course_name, course_id, deadline in (await session.exec(
                select(AnalysisTask.analysis_task_id, AnalysisTask.analysis_task_title, Course.course_name,
                       Course.course_id, AnalysisTask.deadline).join(Course,
                                                                     AnalysisTask.course_id == Course.course_id).where(
                    AnalysisTask.course_id.in_(course_ids),
                    (AnalysisTask.deadline.is_(None)) | (AnalysisTask.deadline >= current_time)).order_by(
                    AnalysisTask.analysis_task_id.desc()))).all() if task_id not in completed_gai_ids_set]
        return {"tasks": todo_tasks, "gai_tasks": todo_gai_tasks}


async def db_report_study_duration(course_id: uuid.UUID, student_id: str, duration: int) -> None:
    """
    函数目的：接收前端分片上报的时长，加锁累加到该学生本周对应星期的学习秒数中（纯整型操作）。
    参数信息：
        - course_id: uuid.UUID，目标课程的唯一标识。
        - student_id: str，发起上报的学生ID。
        - duration: int，本次增量学习时长（秒），由上层 Pydantic 保证大于 0。
    """
    weekday_idx = datetime.now(UTC).weekday()

    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course:
            raise AppBusinessException(404, "课程不存在")

        if not (await session.exec(
                select(CourseRegistrationRecord.registration_id).where(
                    CourseRegistrationRecord.student_id == student_id,
                    CourseRegistrationRecord.course_id == course_id
                )
        )).first():
            raise AppBusinessException(403, "无权访问此课程")

        statement = (
            select(StudentDailyStudyTimeInCourse)
            .where(
                StudentDailyStudyTimeInCourse.student_id == student_id,
                StudentDailyStudyTimeInCourse.course_id == course_id
            )
            .with_for_update()
        )

        record = (await session.exec(statement)).one_or_none()

        if not record:
            study_data = [0] * 7
            study_data[weekday_idx] += int(duration)
            session.add(
                StudentDailyStudyTimeInCourse(
                    student_id=student_id,
                    course_id=course_id,
                    study_data=study_data
                )
            )
        else:
            current_data = record.study_data
            if not isinstance(current_data, list) or len(current_data) != 7:
                current_data = [0] * 7

            original_val = current_data[weekday_idx]
            current_data[weekday_idx] = (int(original_val) if original_val else 0) + int(duration)

            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(record, "study_data")
            session.add(record)

        await session.commit()


async def db_get_student_course_context_for_analysis(
        course_id: str,
        student_id: str,
        current_task_id: int,
        current_task_results: list
) -> dict | None:
    """
    函数目的：聚合学生在该课程的所有学习上下文，供学情分析使用。提取人类可读的名称与选项内容，彻底消除冷冰冰的 ID。
    参数信息：
    - course_id: str, 课程 UUID 字符串
    - student_id: str, 学生 ID
    - current_task_id: int, 当前刚批改完的任务 ID
    - current_task_results: list, 当前任务各题的得分详情列表
    返回值：结构化的上下文字典，无数据时返回 None。
    """
    from sqlmodel import select

    async with async_session_factory() as session:
        course_uuid = uuid.UUID(course_id)

        # 0. 获取基础身份信息
        course = await session.get(Course, course_uuid)
        if not course:
            return None
        student = await session.get(Student, student_id)
        if not student:
            return None

        # 1. 获取章节完成情况与难度反馈（关联章节名）
        sections_data = []
        section_records = (
            await session.exec(
                select(SectionCompletionRecord, Section.section_title, Section.description, Chapter.chapter_title)
                .join(Section, SectionCompletionRecord.section_id == Section.section_id)
                .join(Chapter, Section.chapter_id == Chapter.chapter_id)
                .where(
                    SectionCompletionRecord.student_id == student_id,
                    Chapter.course_id == course_uuid
                )
            )
        ).all()

        for rec, title, desc, chapter_title in section_records:
            sections_data.append({
                "chapter_name": chapter_title,
                "section_title": title,
                "description": desc,
                "is_completed": True,
                "learning_effect": rec.learning_effect
            })

        # 2. 获取所有已完成的测验任务情况（替换选项 ID 为文本）
        tasks_data = []
        all_completions = (
            await session.exec(
                select(TaskCompletion).where(
                    TaskCompletion.student_id == student_id,
                    TaskCompletion.task_id.in_(
                        select(Task.task_id).where(Task.course_id == course_uuid)
                    )
                )
            )
        ).all()

        for comp in all_completions:
            task = await session.get(Task, comp.task_id)
            if not task:
                continue

            quiz_items = task.quiz or []
            std_ans_items = task.answer or []
            stu_ans_items = comp.answer or []

            std_answer_map = {
                item.get("question_id"): item.get("correct_answer")
                for item in std_ans_items if isinstance(item, dict) and item.get("question_id")
            }
            student_answer_map = {
                item.get("question_id"): item.get("answer")
                for item in stu_ans_items if isinstance(item, dict) and item.get("question_id")
            }

            questions_detail = []
            for q in quiz_items:
                if not isinstance(q, dict) or not q.get("question_id"):
                    continue
                q_id = q.get("question_id")

                # 核心优化：构建当前题目的选项 ID -> 文本 映射表
                options_map = {}
                raw_options = q.get("options") or []
                clean_options_for_ai = []  # 给 AI 看的纯净选项列表

                for opt in raw_options:
                    if isinstance(opt, dict) and opt.get("id") and opt.get("content"):
                        options_map[opt["id"]] = opt["content"]
                        clean_options_for_ai.append({"content": opt["content"]})

                std_ans_text = std_answer_map.get(q_id)
                stu_ans_text = student_answer_map.get(q_id)

                readable_std_ans = _replace_id_with_content(std_ans_text, options_map) if std_ans_text else None
                readable_stu_ans = _replace_id_with_content(stu_ans_text, options_map) if stu_ans_text else None

                q_detail = {
                    "type": q.get("type"),
                    "title": q.get("title"),
                    "options": clean_options_for_ai,
                    "correct_answer": readable_std_ans,
                    "student_answer": readable_stu_ans
                }
                if task.task_id == current_task_id:
                    res = next((r for r in current_task_results if str(r.get("question_id")) == str(q_id)), None)
                    if res:
                        q_detail["score"] = res.get("score")
                        q_detail["is_ai_graded"] = res.get("is_ai_graded")

                questions_detail.append(q_detail)

            tasks_data.append({
                "task_title": task.task_title,
                "final_score": comp.task_scores,
                "questions_detail": questions_detail
            })

        if not sections_data and not tasks_data:
            return None

        return {
            "student_name": student.username,
            "course_name": course.course_name,
            "learning_progress": sections_data,
            "tasks_performance": tasks_data
        }


def _replace_id_with_content(answer, options_map: dict) -> str | list[str] | None:
    """函数目的：纯内存工具，将答案中的选项 ID 替换为具体的选项文本内容。
    参数信息：
    - answer: str | list[str] | None，学生或教师的原始答案
    - options_map: dict，选项 ID 到文本的映射字典
    返回值：替换后的文本、文本列表或原值。
    """
    if not answer:
        return answer
    if isinstance(answer, list):
        return [options_map.get(item, item) for item in answer]
    if isinstance(answer, str):
        return options_map.get(answer, answer)
    return answer


async def db_upsert_student_analysis_description(course_id: str, student_id: str, analysis_content: str) -> None:
    """函数目的：更新或插入学生的课程学情分析记录。
    参数信息：- course_id: str, - student_id: str, - analysis_content: str
    返回值：无。
    """
    from sqlmodel import select
    async with async_session_factory() as session:
        course_uuid = uuid.UUID(course_id)
        existing = (await session.exec(
            select(AnalysisDescription).where(
                AnalysisDescription.student_id == student_id,
                AnalysisDescription.course_id == course_uuid
            ).order_by(AnalysisDescription.analysis_id.desc())
        )).first()
        if existing:
            existing.analysis_content = analysis_content
            session.add(existing)
        else:
            new_record = AnalysisDescription(
                student_id=student_id,
                course_id=course_uuid,
                analysis_content=analysis_content
            )
            session.add(new_record)
        await session.commit()


#  定时任务：全班学情分析数据拉取 

async def db_get_all_active_course_ids() -> list[uuid.UUID]:
    """函数目的：获取系统中所有课程的 ID 列表。
    返回值：list[uuid.UUID]
    """
    from sqlmodel import select
    async with async_session_factory() as session:
        return (await session.exec(select(Course.course_id))).all()


async def db_get_course_full_context_for_teacher_analysis(course_id: uuid.UUID) -> dict | None:
    """函数目的：提取单个课程的全量结构化数据，供大模型生成教学分析。
    参数信息：- course_id: uuid.UUID
    """
    from sqlmodel import select
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if not course:
            return None

        students = (await session.exec(
            select(Student.id, Student.username).join(
                CourseRegistrationRecord, Student.id == CourseRegistrationRecord.student_id
            ).where(CourseRegistrationRecord.course_id == course_id)
        )).all()
        if not students:
            return None

        student_map = {s_id: s_name for s_id, s_name in students}

        # 2. 拉取所有章节及小节
        chapters_data = []
        chapters = (await session.exec(
            select(Chapter).where(Chapter.course_id == course_id).order_by(Chapter.chapter_order)
        )).all()

        for ch in chapters:
            sections = (await session.exec(
                select(Section).where(Section.chapter_id == ch.chapter_id).order_by(Section.section_order)
            )).all()

            sections_data = []
            for sec in sections:
                # 获取该小节所有学生的完成情况
                completions = (await session.exec(
                    select(SectionCompletionRecord).where(SectionCompletionRecord.section_id == sec.section_id)
                )).all()

                sec_stats = []
                for comp in completions:
                    sec_stats.append({
                        "student_id": comp.student_id,
                        "student_name": student_map.get(comp.student_id, "未知学生"),
                        "is_completed": True,
                        "learning_effect": comp.learning_effect,
                    })

                sections_data.append({
                    "section_id": sec.section_id,
                    "section_title": sec.section_title,
                    "description": sec.description,
                    "student_stats": sec_stats
                })

            chapters_data.append({
                "chapter_id": ch.chapter_id,
                "chapter_title": ch.chapter_title,
                "sections": sections_data
            })

        # 3. 拉取所有测验任务及学生作答
        tasks_data = []
        tasks = (await session.exec(select(Task).where(Task.course_id == course_id))).all()

        for task in tasks:
            completions = (await session.exec(
                select(TaskCompletion).where(TaskCompletion.task_id == task.task_id)
            )).all()

            stu_completions_data = []
            for comp in completions:
                stu_completions_data.append({
                    "student_id": comp.student_id,
                    "student_name": student_map.get(comp.student_id, "未知学生"),
                    "answers": comp.answer,
                    "score": comp.task_scores
                })

            tasks_data.append({
                "task_id": task.task_id,
                "task_title": task.task_title,
                "quiz": task.quiz,
                "answer": task.answer,
                "student_completions": stu_completions_data
            })

        return {
            "course_name": course.course_name,
            "teaching_plan": course.teaching_plan,
            "chapters": chapters_data,
            "tasks": tasks_data
        }


async def db_update_course_teaching_analysis(course_id: uuid.UUID, analysis_text: str) -> None:
    """函数目的：更新课程的 teaching_analysis 字段。
    参数信息：- course_id: uuid.UUID, - analysis_text: str
    """
    async with async_session_factory() as session:
        course = await session.get(Course, course_id)
        if course:
            course.teaching_analysis = analysis_text
            session.add(course)
            await session.commit()


#  管理端：分页与更新核心逻辑 

async def db_get_organizations_page(page: int, size: int = 30, keyword: str | None = None) -> dict:
    """函数目的：分页获取组织列表，支持按名称模糊搜索（管理后台与登录页共用）。
    参数信息：
        - page: int, 当前页码，从 1 开始。
        - size: int, 每页数量。
        - keyword: str | None, 搜索关键词。
    返回值：dict, 包含 list 和 total 的分页字典。
    """
    async with async_session_factory() as session:
        base_stmt = select(Organization)
        count_stmt = select(func.count()).select_from(Organization)

        if keyword:
            like_pattern = f"%{keyword}%"
            base_stmt = base_stmt.where(Organization.organization_name.like(like_pattern))
            count_stmt = count_stmt.where(Organization.organization_name.like(like_pattern))

        total = (await session.exec(count_stmt)).one()
        offset = (page - 1) * size
        statement = base_stmt.order_by(Organization.organization_id).offset(offset).limit(size)
        organizations = (await session.exec(statement)).all()

        # 严格隔离 ORM 对象，ID 转 str，枚举转 value
        result_list = [
            {
                "organization_id": str(org.organization_id),
                "organization_name": org.organization_name,
                "prefix": org.prefix,
                "phase": org.phase.value
            }
            for org in organizations
        ]
        return {"list": result_list, "total": total}



async def db_update_organization(org_id: int, update_data: dict) -> None:
    """函数目的：更新组织基础信息。
    参数信息：
        - org_id: int, 组织ID。
        - update_data: dict, 允许更新的字段字典。
    返回值：无。
    """
    async with async_session_factory() as session:
        org = await session.get(Organization, org_id)
        if not org:
            raise AppBusinessException(404, "组织不存在")
        for key, value in update_data.items():
            if hasattr(org, key) and value is not None:
                setattr(org, key, value)
        session.add(org)
        await session.commit()


async def db_get_classes_page(organization_id: int, page: int, size: int = 30, keyword: str | None = None) -> dict:
    """函数目的：分页获取指定组织下的班级列表。
    参数信息：
        - organization_id: int, 组织ID（必传筛选）。
        - page: int, 当前页码。
        - size: int, 每页数量。
        - keyword: str | None, 班级名称搜索词。
    返回值：dict, 包含 list 和 total 的分页字典。
    """
    async with async_session_factory() as session:
        base_stmt = select(StudentClass).where(StudentClass.organization_id == organization_id)
        count_stmt = select(func.count()).select_from(StudentClass).where(
            StudentClass.organization_id == organization_id)

        if keyword:
            like_pattern = f"%{keyword}%"
            base_stmt = base_stmt.where(StudentClass.class_name.like(like_pattern))
            count_stmt = count_stmt.where(StudentClass.class_name.like(like_pattern))

        total = (await session.exec(count_stmt)).one()
        offset = (page - 1) * size
        statement = base_stmt.order_by(StudentClass.class_id).offset(offset).limit(size)
        classes = (await session.exec(statement)).all()

        result_list = [ClassRead.model_validate(c).model_dump(mode='json') for c in classes]
        return {"list": result_list, "total": total}


async def db_create_class_direct(class_name: str, organization_id: int) -> int:
    """函数目的：管理员直接通过ID创建班级（跳过名称查重，提升精准度）。
    参数信息：
        - class_name: str, 班级名称。
        - organization_id: int, 组织ID。
    返回值：int, 新建的班级ID。
    """
    async with async_session_factory() as session:
        new_class = StudentClass(class_name=class_name, organization_id=organization_id)
        session.add(new_class)
        await session.commit()
        await session.refresh(new_class)
        return new_class.class_id


async def db_update_class(class_id: int, update_data: dict) -> None:
    """函数目的：更新班级名称。
    参数信息：
        - class_id: int, 班级ID。
        - update_data: dict, 允许更新的字段字典。
    返回值：无。
    """
    async with async_session_factory() as session:
        db_class = await session.get(StudentClass, class_id)
        if not db_class:
            raise AppBusinessException(404, "班级不存在")
        for key, value in update_data.items():
            if hasattr(db_class, key) and value is not None:
                setattr(db_class, key, value)
        session.add(db_class)
        await session.commit()


async def db_get_teachers_page(organization_id: int, page: int, size: int = 30, keyword: str | None = None) -> dict:
    """函数目的：分页获取指定组织下的教师列表。
    参数信息：
        - organization_id: int, 组织ID（必传筛选）。
        - page: int, 当前页码。
        - size: int, 每页数量。
        - keyword: str | None, 教师ID或姓名搜索词。
    返回值：dict, 包含 list 和 total 的分页字典。
    """
    async with async_session_factory() as session:
        base_stmt = select(Teacher).where(Teacher.organization_id == organization_id)
        count_stmt = select(func.count()).select_from(Teacher).where(Teacher.organization_id == organization_id)

        if keyword:
            like_pattern = f"%{keyword}%"
            filter_cond = or_(Teacher.id.like(like_pattern), Teacher.username.like(like_pattern))
            base_stmt = base_stmt.where(filter_cond)
            count_stmt = count_stmt.where(filter_cond)

        total = (await session.exec(count_stmt)).one()
        offset = (page - 1) * size
        statement = base_stmt.order_by(Teacher.id).offset(offset).limit(size)
        teachers = (await session.exec(statement)).all()

        result_list = [
            {"id": t.id, "username": t.username, "organization_id": t.organization_id}
            for t in teachers
        ]
        return {"list": result_list, "total": total}


async def db_update_teacher(teacher_id: str, update_data: dict) -> None:
    """函数目的：更新教师基础信息。
    参数信息：
        - teacher_id: str, 教师ID。
        - update_data: dict, 允许更新的字段字典（不含组织ID）。
    返回值：无。
    """
    async with async_session_factory() as session:
        teacher = await session.get(Teacher, teacher_id)
        if not teacher:
            raise AppBusinessException(404, "教师不存在")
        for key, value in update_data.items():
            if hasattr(teacher, key) and value is not None:
                setattr(teacher, key, value)
        session.add(teacher)
        await session.commit()


async def db_get_students_page(class_id: int, page: int, size: int = 30, keyword: str | None = None) -> dict:
    """函数目的：分页获取指定班级下的学生列表。
    参数信息：
        - class_id: int, 班级ID（必传筛选）。
        - page: int, 当前页码。
        - size: int, 每页数量。
        - keyword: str | None, 学生ID或姓名搜索词。
    返回值：dict, 包含 list 和 total 的分页字典。
    """
    async with async_session_factory() as session:
        base_stmt = select(Student).where(Student.class_id == class_id)
        count_stmt = select(func.count()).select_from(Student).where(Student.class_id == class_id)

        if keyword:
            like_pattern = f"%{keyword}%"
            filter_cond = or_(Student.id.like(like_pattern), Student.username.like(like_pattern))
            base_stmt = base_stmt.where(filter_cond)
            count_stmt = count_stmt.where(filter_cond)

        total = (await session.exec(count_stmt)).one()
        offset = (page - 1) * size
        statement = base_stmt.order_by(Student.id).offset(offset).limit(size)
        students = (await session.exec(statement)).all()

        result_list = [
            {
                "id": s.id,
                "username": s.username,
                "class_id": s.class_id,
                "organization_id": s.organization_id
            }
            for s in students
        ]
        return {"list": result_list, "total": total}


async def db_update_student(student_id: str, update_data: dict, target_class_id: int | None = None) -> None:
    """函数目的：更新学生信息，并在变更班级时执行严格的跨组织阻断校验。
    参数信息：
        - student_id: str, 学生ID。
        - update_data: dict, 允许更新的基础字段字典。
        - target_class_id: int | None, 目标班级ID，为None时不修改班级。
    返回值：无。
    """
    async with async_session_factory() as session:
        student = await session.get(Student, student_id)
        if not student:
            raise AppBusinessException(404, "学生不存在")

        if target_class_id is not None:
            target_class = await session.get(StudentClass, target_class_id)
            if not target_class:
                raise AppBusinessException(404, "目标班级不存在")
            if target_class.organization_id != student.organization_id:
                raise AppBusinessException(400, "禁止跨组织转班")
            student.class_id = target_class_id

        for key, value in update_data.items():
            if hasattr(student, key) and value is not None:
                setattr(student, key, value)
        session.add(student)
        await session.commit()
