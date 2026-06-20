import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, SMALLINT, TEXT, Column, DateTime, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, Relationship, SQLModel

from app.schema.enums import PhaseType, ResourceType


class Organization(SQLModel, table=True):
    """ 组织表 """
    __tablename__ = "organization"
    organization_id: int | None = Field(primary_key=True, default=None)
    organization_name: str = Field(max_length=255, unique=True)

    phase: PhaseType = Field(sa_column=Column(SAEnum(PhaseType, name="phase_type_enum")))
    prefix: str = Field(default="", max_length=50, description="登录前缀")

    classes: list[StudentClass] = Relationship(back_populates="organization", passive_deletes="all",
                                                 sa_relationship_kwargs={"lazy": "raise"})
    teachers: list[Teacher] = Relationship(back_populates="organization", sa_relationship_kwargs={"lazy": "raise"})
    students: list[Student] = Relationship(back_populates="organization", passive_deletes="all",
                                             sa_relationship_kwargs={"lazy": "raise"})


class StudentClass(SQLModel, table=True):
    """ 班级表 """
    __tablename__ = "student_class"
    class_id: int | None = Field(primary_key=True, default=None)
    class_name: str = Field(max_length=255)
    organization_id: int = Field(index=True, foreign_key="organization.organization_id", ondelete="CASCADE")

    organization: Organization = Relationship(back_populates="classes", passive_deletes="all",
                                              sa_relationship_kwargs={"lazy": "raise"})
    students: list[Student] = Relationship(back_populates="my_class", passive_deletes="all",
                                             sa_relationship_kwargs={"lazy": "raise"})


class UserSQLBase(SQLModel):
    id: str = Field(primary_key=True)
    username: str = Field(max_length=255)
    hashed_password: str = Field()


class Student(UserSQLBase, table=True):
    """ student 数据表 """
    __tablename__ = "student"
    class_id: int = Field(foreign_key="student_class.class_id", ondelete="CASCADE")
    organization_id: int = Field(foreign_key="organization.organization_id", ondelete="CASCADE")

    my_class: StudentClass = Relationship(back_populates="students", passive_deletes="all",
                                          sa_relationship_kwargs={"lazy": "raise"})
    organization: Organization = Relationship(back_populates="students", passive_deletes="all",
                                              sa_relationship_kwargs={"lazy": "raise"})
    courses: list[CourseRegistrationRecord] = Relationship(back_populates="student", passive_deletes="all",
                                                             sa_relationship_kwargs={"lazy": "raise"})
    section_completions: list[SectionCompletionRecord] = Relationship(back_populates="student", passive_deletes="all",
                                                                        sa_relationship_kwargs={"lazy": "raise"})
    task_completions: list[TaskCompletion] = Relationship(back_populates="student", passive_deletes="all",
                                                            sa_relationship_kwargs={"lazy": "raise"})
    GAI_task_completions: list[AnalysisTaskCompletion] = Relationship(back_populates="student", passive_deletes="all",
                                                                        sa_relationship_kwargs={"lazy": "raise"})
    daily_study: list[StudentDailyStudyTimeInCourse] = Relationship(back_populates="student", passive_deletes="all",
                                                                      sa_relationship_kwargs={"lazy": "raise"})
    analysis_descriptions: list[AnalysisDescription] = Relationship(back_populates="student", passive_deletes="all",
                                                                      sa_relationship_kwargs={"lazy": "raise"})


class Teacher(UserSQLBase, table=True):
    """ teacher 数据表 """
    __tablename__ = "teacher"
    organization_id: int = Field(foreign_key="organization.organization_id", ondelete="CASCADE")

    organization: Organization | None = Relationship(back_populates="teachers", passive_deletes="all",
                                                        sa_relationship_kwargs={"lazy": "raise"})
    courses: list[Course] = Relationship(back_populates="teacher", passive_deletes="all",
                                           sa_relationship_kwargs={"lazy": "raise"})


class Admin(UserSQLBase, table=True):
    """ admin 数据表 """
    __tablename__ = "admin"


class Course(SQLModel, table=True):
    """ 课程数据表 ：老师创建课程"""
    __tablename__ = "course"
    course_id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    course_name: str = Field(max_length=255)
    teacher_id: str = Field(index=True, foreign_key="teacher.id", ondelete="CASCADE")
    course_cover: str = Field(default="covers/default.png", max_length=500)
    teaching_plan: str = Field(sa_column=Column(TEXT), default="暂无教学计划")
    invited_code: str = Field(default_factory=lambda: uuid.uuid4().hex[:8], unique=True, index=True)
    is_invitation_valid: bool = Field(default=False, description="邀请码是否有效")
    teaching_analysis: str | None = Field(default=None, sa_column=Column(TEXT), description="GAI分析教学分析")

    teacher: Teacher = Relationship(back_populates="courses", sa_relationship_kwargs={"lazy": "raise"})
    students: list[CourseRegistrationRecord] = Relationship(back_populates="course", passive_deletes="all",
                                                              sa_relationship_kwargs={"lazy": "raise"})
    chapters: list[Chapter] = Relationship(back_populates="course", passive_deletes="all",
                                             sa_relationship_kwargs={"lazy": "raise"})
    tasks: list[Task] = Relationship(back_populates="course", passive_deletes="all",
                                       sa_relationship_kwargs={"lazy": "raise"})
    GAI_task: list[AnalysisTask] = Relationship(back_populates="course", passive_deletes="all",
                                                  sa_relationship_kwargs={"lazy": "raise"})
    GAI_task_completions: list[AnalysisTaskCompletion] = Relationship(back_populates="course", passive_deletes="all",
                                                                        sa_relationship_kwargs={"lazy": "raise"})
    analysis_descriptions: list[AnalysisDescription] = Relationship(back_populates="course", passive_deletes="all",
                                                                      sa_relationship_kwargs={"lazy": "raise"})
    daily_study: list[StudentDailyStudyTimeInCourse] = Relationship(back_populates="course", passive_deletes="all",
                                                                      sa_relationship_kwargs={"lazy": "raise"})


class CourseRegistrationRecord(SQLModel, table=True):
    """ 存储课程中学生信息信息 where course_id -> list[student] """
    __tablename__ = "course_registration_record"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_student_course"),
    )
    registration_id: int | None = Field(primary_key=True, default=None)
    student_id: str = Field(foreign_key="student.id", ondelete="CASCADE")
    course_id: uuid.UUID = Field(index=True, foreign_key="course.course_id", ondelete="CASCADE")

    student: Student = Relationship(back_populates="courses", passive_deletes="all",
                                    sa_relationship_kwargs={"lazy": "raise"})
    course: Course = Relationship(back_populates="students", passive_deletes="all",
                                  sa_relationship_kwargs={"lazy": "raise"})


class Chapter(SQLModel, table=True):
    """章节数据表"""
    __tablename__ = "chapter"
    __table_args__ = (
        UniqueConstraint("course_id", "chapter_order", name="uq_course_chapter_order"),
    )
    chapter_id: int | None = Field(primary_key=True, default=None)
    course_id: uuid.UUID = Field(index=True, foreign_key="course.course_id", ondelete="CASCADE")
    chapter_title: str = Field(max_length=255)
    chapter_order: int = Field()

    course: Course = Relationship(back_populates="chapters", passive_deletes="all",
                                  sa_relationship_kwargs={"lazy": "raise"})
    sections: list[Section] = Relationship(back_populates="chapter", passive_deletes="all",
                                             sa_relationship_kwargs={"lazy": "raise"})


class Section(SQLModel, table=True):
    """ 小节数据表 """
    __tablename__ = "section"
    __table_args__ = (
        UniqueConstraint("chapter_id", "section_order", name="uq_chapter_section_order"),
    )
    section_id: int | None = Field(primary_key=True, default=None)
    chapter_id: int = Field(index=True, foreign_key="chapter.chapter_id", ondelete="CASCADE")
    section_title: str = Field(max_length=255)
    section_type: ResourceType = Field(sa_column=Column(SAEnum(ResourceType)))
    resource_path: str = Field()
    description: str = Field(default="", sa_column=Column(TEXT))
    section_order: int = Field()

    chapter: Chapter = Relationship(back_populates="sections", sa_relationship_kwargs={"lazy": "raise"})
    section_completions: list[SectionCompletionRecord] = Relationship(back_populates="section", passive_deletes="all",
                                                                        sa_relationship_kwargs={"lazy": "raise"})


class SectionCompletionRecord(SQLModel, table=True):
    """ 小节完成记录 """
    __tablename__ = "section_completion_record"
    completion_id: int | None = Field(primary_key=True, default=None)
    section_id: int = Field(foreign_key="section.section_id", ondelete="CASCADE")
    student_id: str = Field(foreign_key="student.id", ondelete="CASCADE")
    learning_effect: int = Field(sa_column=Column(SMALLINT))

    section: Section = Relationship(back_populates="section_completions", sa_relationship_kwargs={"lazy": "raise"})
    student: Student = Relationship(back_populates="section_completions", sa_relationship_kwargs={"lazy": "raise"})

class Task(SQLModel, table=True):
    """ 全部课程的任务 """
    __tablename__ = "task"
    task_id: int | None = Field(primary_key=True, default=None)
    task_title: str = Field(max_length=255)
    course_id: uuid.UUID = Field(index=True, foreign_key="course.course_id", ondelete="CASCADE")
    deadline: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    quiz: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    answer: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    course: Course = Relationship(back_populates="tasks", sa_relationship_kwargs={"lazy": "raise"})
    task_completions: list[TaskCompletion] = Relationship(back_populates="task", passive_deletes="all",
                                                                sa_relationship_kwargs={"lazy": "raise"})

class TaskCompletion(SQLModel, table=True):
    """ 任务完成记录 """
    __tablename__ = "task_completion"
    completion_id: int | None = Field(primary_key=True, default=None)
    task_id: int = Field(foreign_key="task.task_id", ondelete="CASCADE")
    student_id: str = Field(foreign_key="student.id", ondelete="CASCADE")
    answer: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    task_scores: int = Field(description="任务得分")
    task_analysis: str | None = Field(default="AI正在分析中", sa_column=Column(TEXT),
                                         description="AI对学生作答的分析")

    task: Task = Relationship(back_populates="task_completions", sa_relationship_kwargs={"lazy": "raise"})
    student: Student = Relationship(back_populates="task_completions", sa_relationship_kwargs={"lazy": "raise"})


class AnalysisTask(SQLModel, table=True):
    """ GAI对话分析任务 """
    __tablename__ = "analysis_task"
    analysis_task_id: int | None = Field(primary_key=True, default=None)
    analysis_task_title: str = Field(max_length=255)
    task_description: str = Field(sa_column=Column(TEXT))
    analysis_description: str = Field(sa_column=Column(TEXT))
    evaluation_criterion: str = Field(sa_column=Column(TEXT))
    deadline: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    course_id: uuid.UUID = Field(index=True, foreign_key="course.course_id", ondelete="CASCADE")
    course: Course = Relationship(back_populates="GAI_task", sa_relationship_kwargs={"lazy": "raise"})
    GAI_task_completions: list[AnalysisTaskCompletion] = Relationship(back_populates="GAI_task", passive_deletes="all", sa_relationship_kwargs={"lazy": "raise"})



class AnalysisTaskCompletion(SQLModel, table=True):
    """ GAI对话分析任务提交 """
    __tablename__ = "analysis_task_completion_record"
    completion_id: int | None = Field(primary_key=True, default=None)
    analysis_task_id: int = Field(foreign_key="analysis_task.analysis_task_id", ondelete="CASCADE")
    student_id: str = Field(foreign_key="student.id", ondelete="CASCADE")
    messages: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON), description="存储对话massages")
    analysis_result: str = Field(sa_column=Column(TEXT), description="massages分析的结果")
    course_id: uuid.UUID = Field(index=True, foreign_key="course.course_id", ondelete="CASCADE")

    GAI_task: AnalysisTask = Relationship(back_populates="GAI_task_completions",
                                          sa_relationship_kwargs={"lazy": "raise"})
    student: Student = Relationship(back_populates="GAI_task_completions", sa_relationship_kwargs={"lazy": "raise"})
    course: Course = Relationship(back_populates="GAI_task_completions", sa_relationship_kwargs={"lazy": "raise"})


class AnalysisDescription(SQLModel, table=True):
    """ GAI 在课程上对学生的学习分析 （每次在学习提交任务时，调用ai模型对学生进行分析）"""
    __tablename__ = "analysis_description"
    analysis_id: int | None = Field(primary_key=True, default=None)
    analysis_content: str = Field(sa_column=Column(TEXT))
    student_id: str = Field(foreign_key="student.id", ondelete="CASCADE")
    course_id: uuid.UUID = Field(index=True, foreign_key="course.course_id", ondelete="CASCADE")

    course: Course = Relationship(back_populates="analysis_descriptions", sa_relationship_kwargs={"lazy": "raise"})
    student: Student = Relationship(back_populates="analysis_descriptions", sa_relationship_kwargs={"lazy": "raise"})


class StudentDailyStudyTimeInCourse(SQLModel, table=True):
    """ 学生每周课程学习时间 """
    __tablename__ = "student_daily_study_time"
    record_id: int | None = Field(primary_key=True, default=None)
    student_id: str = Field(index=True, foreign_key="student.id", ondelete="CASCADE")
    course_id: uuid.UUID = Field(index=True, foreign_key="course.course_id", ondelete="CASCADE")
    study_data: list[int | None] | None = Field(default=None, sa_column=Column(JSON),
                                                   description="周一到周日的学习时间(秒)")
    student: Student = Relationship(back_populates="daily_study", passive_deletes="all",
                                    sa_relationship_kwargs={"lazy": "raise"})
    course: Course = Relationship(back_populates="daily_study", passive_deletes="all",
                                  sa_relationship_kwargs={"lazy": "raise"})
