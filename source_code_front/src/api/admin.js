import request from "../utils/request";

/** 管理员鉴权 */
export function adminAuth(payload) {
    return request.post("auth/token", payload);
}

/** 组织管理 */
export function getOrganizationsPage(params) {
    return request.get("admin/organization/page", {params});
}

export function createOrganization(data) {
    return request.post("admin/organization/new", data);
}

export function updateOrganization(data) {
    return request.patch("admin/organization/update", data);
}

export function deleteOrganization(data) {
    return request.delete("admin/organization/delete", {data});
}

/** 班级管理 */
export function getClassesPage(params) {
    return request.get("admin/class/page", {params});
}

export function createClass(data) {
    return request.post("admin/class/new", data);
}

export function updateClass(data) {
    return request.patch("admin/class/update", data);
}

export function deleteClass(data) {
    return request.delete("admin/class/delete", {data});
}

/** 学生管理 */
export function getStudentsPage(params) {
    return request.get("admin/user/page/student", {params});
}

export function createStudent(data) {
    return request.post("admin/user/new/student", data);
}

export function updateStudent(data) {
    return request.patch("admin/user/update/student", data);
}

export function deleteStudent(data) {
    return request.delete("admin/user/delete/student", {data});
}

/** 教师管理 */
export function getTeachersPage(params) {
    return request.get("admin/user/page/teacher", {params});
}

export function createTeacher(data) {
    return request.post("admin/user/new/teacher", data);
}

export function updateTeacher(data) {
    return request.patch("admin/user/update/teacher", data);
}

export function deleteTeacher(data) {
    return request.delete("admin/user/delete/teacher", {data});
}