// src/api/common.js
import request from "../utils/request";

/**
 * @description 用户登录鉴权获取 Token（支持动态验证码参数）
 * @method POST /auth/token
 * @requestParams { string } id - 学号或工号
 * @requestParams { string } password - 密码
 * @requestParams { string } role - 角色，固定传 "student" 或 "teacher"
 * @requestParams { string } [captcha_key] - 验证码 Key（后端要求时必传）
 * @requestParams { string } [captcha_code] - 验证码计算结果（后端要求时必传）
 * @response { code: number, data: { access_token: string, role: string, username: string, id: string, user_class: string } | { need_captcha: boolean, locked: boolean, lock_ttl: number } }
 * @interactionNotes 登录成功前端需将 data 下的字段存入 localStorage。业务错误（HTTP 200）由调用方解析 res. Data 指令处理 UI。
 */
export function auth(payload) {
  return request.post("auth/token", payload);
}

/**
 * @description 获取图形验证码
 * @method GET /auth/captcha
 * @response { code: number, data: { captcha_key: string, captcha_image: string } }
 * @interactionNotes 返回的 image 为 Base64 格式，前端直接绑定至 img 标签 src。
 */
export function getCaptcha() {
  return request.get("auth/captcha");
}

/**
 * @description 分页获取机构列表，支持关键字后端过滤
 * @method GET /organization/get
 * @requestParams { number } page - 当前页码，从 1 开始
 * @requestParams { string } keyword - 搜索关键词（可选）
 * @response { code: number, data: { list: Array<{organization_id: number, organization_name: string, prefix: string}> } }
 * @interactionNotes 后端固定分页大小 size=30。前端通过判断返回数组长度是否小于30来判定是否到底。
 */
export function getOrganizations(page, keyword) {
  return request.get("organization/get", { params: { page: page, keyword: keyword || '' } });
}

/** ... (原有的 auth, getCaptcha, getOrganizations 函数保持不变) ... */

/**
 * @description 修改当前用户密码
 * @method POST /auth/password
 * @requestParams { string } old_password - 用户当前的原密码
 * @requestParams { string } new_password - 用户新设置的密码
 * @response { code: number, message: string, data: object }
 * @interactionNotes 调用成功后前端将执行登出逻辑。后端需校验原密码正确性。
 */
export function updatePassword(payload) {
  return request.post("auth/password", payload);
}