// src/utils/sseRequest.js
import { showToast } from 'vant'

/**
 * 适用于 @microsoft/fetch-event-source 的自定义 fetch 封装
 * 目的：复用全局 Token 注入逻辑、基础路径与基础 HTTP 错误提示，对业务层屏蔽细节
 * @param {string} url - 请求地址（相对路径如 /xxx 或完整路径）
 * @param {RequestInit} options - 原生 fetch 配置项
 * @returns {Promise<Response>} 原生 fetch 响应对象
 */
/**
 * 适用于 @microsoft/fetch-event-source 的自定义 fetch 封装
 * 目的：复用全局 Token 注入逻辑、基础路径与基础 HTTP 错误提示，对业务层屏蔽细节
 * @param {string} url - 请求地址（相对路径如 /xxx 或完整路径）
 * @param {RequestInit} options - 原生 fetch 配置项
 * @returns {Promise<Response>} 原生 fetch 响应对象
 */
export const sseFetch = async (url, options) => {
  const baseURL = import.meta.env.VITE_API_BASE_URL || "/"
  const finalUrl = url.startsWith('http') ? url : `${baseURL}${url}`
  const token = localStorage.getItem('token')

  const originalHeaders = options.headers || {}
  const headers = {
    ...originalHeaders
  }

  // 如果 body 不是 FormData，则默认设置 Content-Type 为 application/json
  // 如果是 FormData，则不设置 Content-Type，让浏览器自动处理 boundary
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = originalHeaders['Content-Type'] || 'application/json'
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  try {
    const response = await window.fetch(finalUrl, { ...options, headers: headers })

    if (!response.ok) {
      let serverMsg = '请求失败'
      try {
        const errorData = await response.json()
        serverMsg = errorData.message || errorData.detail || serverMsg
      } catch (e) {
        // JSON 解析失败则使用默认提示
      }

      switch (response.status) {
        case 400:
          showToast(serverMsg || '请求参数有误')
          break
        case 401:
          localStorage.clear()
          showToast('登录已过期，请重新登录')
          setTimeout(() => {
            if (window.location.pathname !== '/') {
              window.location.href = '/'
            }
          }, 1500)
          break
        case 403:
          showToast('没有权限进行此操作')
          setTimeout(() => { window.history.back() }, 2000)
          break
        case 404:
          showToast('请求的资源不存在')
          break
        case 429:
          showToast('请求过于频繁，请稍后再试')
          break
        case 500:
          showToast('服务器内部错误')
          break
        default:
          showToast(serverMsg)
      }
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    return response
  } catch (error) {
    if (error.message.includes('HTTP error')) {
      throw error
    }
    showToast('网络异常，请检查网络连接')
    throw error
  }
}
