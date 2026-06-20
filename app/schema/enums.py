from enum import Enum


class RoleType(str, Enum):
    """用户类型"""
    student = "student"
    teacher = "teacher"
    admin = "admin"


class PhaseType(str, Enum):
    """适用学段类型"""
    primary = "小学"
    junior = "初中"
    senior = "高中"
    university = "大学"


class ScenarioType(Enum):
    normal = "normal"
    agi = "agi"


class ResourceType(str, Enum):
    """资源类型"""
    pdf = "pdf"
    video = "video"


class ExamType(str, Enum):
    """测试题型"""
    single = "single"
    multiple = "multiple"
    judge = "judge"
    subjective = "subjective"
