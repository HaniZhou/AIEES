import request from "@/utils/request.js";

/**
 * @description 获取学生本周每日学习时长 #给学生端使用，直接获取一周每天的学习时长数据
 * @method GET /student/weekly-study
 * @response { code: number, data: number[] }
 * @interactionNotes data 直接是一个长度为 7 的浮点数数组（代表周一到周日的小时数，如 [1.5, 2.0, 0.5, ...]），不再有 daily_hours 嵌套。
 */
export function get_student_weekly_study() {
    return request.get(`/student/weekly-study`);
}

/**
 * 获取某学生在某课程中的周学习时长（周一至周日，共7天）
 * @param {number|string} courseId - 课程ID
 * @param {number|string} studentId - 学生ID
 * @returns {Promise} 信封结构响应
 */
export const get_student_weekly_study_in_course = (courseId, studentId) => {
    return request({
        url: `/student/${studentId}/course/${courseId}/weekly-study`,
        method: 'get'
    })
}