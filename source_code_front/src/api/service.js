// src/api/service.js
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { sseFetch } from '@/utils/sseRequest'


export const chatStream = async ({url, messages, signal }, { onToken, onDone, onError }) => {
  let isStreamFinished = false

  try {
    await fetchEventSource(url, {
      method: 'POST',
      body: JSON.stringify({ messages }),
      openWhenHidden: true, // 允许在后台保持连接
      signal: signal,       // 注入中断信号
      fetch: sseFetch,

      onmessage(ev) {
        if (ev.event === 'token') {
          const parsedData = JSON.parse(ev.data)
          onToken?.(parsedData.content)
        } else if (ev.event === 'done') {
          if (JSON.parse(ev.data) === "[DONE]") {
            isStreamFinished = true
            onDone?.()
          }
        } else if (ev.event === 'error') {
          isStreamFinished = true
          const errData = JSON.parse(ev.data)
          onError?.(errData.message || 'AI 服务出现异常', 'BUSINESS')
          throw new Error('BACKEND_BUSINESS_ERROR') // 抛出特定错误中断 fetchEventSource
        }
      },

      onerror(err) {
        // 如果是业务错误或已正常结束，直接抛出，不重试
        if (err.message === 'BACKEND_BUSINESS_ERROR' || isStreamFinished) {
          throw err
        }
        // 网络层错误
        onError?.('网络异常，请检查网络连接', 'NETWORK')
        throw new Error('SSE_NETWORK_ERROR')
      }
    })
  } catch (error) {
    // 如果是用户主动取消，则静默处理
    if (error.name === 'AbortError') return
    // 其他错误已被 onError 捕获并处理，这里仅做异常阻断
  }
}


/**
 * 语音流式识别接口
 * @param {Object} param0 - 请求参数
 * @param {FormData} param0.formData - 包含音频文件的 FormData
 * @param {AbortSignal} param0.signal - 中断信号
 * @param {Object} param1 - 回调函数集合
 * @param {Function} param1.onToken - 识别出文本片段时的回调
 * @param {Function} param1.onDone - 识别完成的回调
 * @param {Function} param1.onError - 发生错误的回调
 */
export const asrStream = async ({ formData, signal }, { onToken, onDone, onError }) => {
  let isStreamFinished = false
  try {
    await fetchEventSource('/service/asr', {
      method: 'POST',
      body: formData,
      openWhenHidden: true,
      signal: signal,
      fetch: sseFetch,
      onmessage(ev) {
        if (ev.event === 'token') {
          const parsedData = JSON.parse(ev.data)
          onToken?.(parsedData.content)
        } else if (ev.event === 'done') {
          if (JSON.parse(ev.data) === "[DONE]") {
            isStreamFinished = true
            onDone?.()
          }
        } else if (ev.event === 'error') {
          isStreamFinished = true
          const errData = JSON.parse(ev.data)
          onError?.(errData.message || '语音识别服务异常', 'BUSINESS')
          throw new Error('BACKEND_BUSINESS_ERROR')
        }
      },
      onerror(err) {
        if (err.message === 'BACKEND_BUSINESS_ERROR' || isStreamFinished) {
          throw err
        }
        onError?.('网络异常，请检查网络连接', 'NETWORK')
        throw new Error('SSE_NETWORK_ERROR')
      }
    })
  } catch (error) {
    if (error.name === 'AbortError') return
  }
}
