<template>
  <div class="agi-container" :class="{ 'is-task-mode': isInTaskMode }">
    <!-- 遮罩层 -->
    <div v-if="isOpen && overlay" class="agi-overlay" @click="handleOverlayClick"></div>
    <div v-show="!hideTrigger" class="agi-trigger" :class="{ 'is-open': isOpen }" @click="togglePanel">
      <svg class="trigger-icon" viewBox="0 0 24 24" width="24" height="24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" fill="white"/>
      </svg>
    </div>
    <transition name="slide">
      <div v-show="isOpen" class="agi-panel">
        <div class="agi-header">
          <div style="flex: 1; min-width: 0;">
            <template v-if="isInTaskMode && taskContext.courseName">
              <div class="task-mode-header">
                <span class="task-course-name">{{ taskContext.courseName }}</span>
                <span class="task-main-title">{{ taskContext.taskTitle }}</span>
              </div>
              <div class="task-desc-text">{{ taskContext.taskDesc }}</div>
            </template>
            <template v-else>
              <div class="header-main">
                <span class="brand-title">探奇</span>
              </div>
            </template>
          </div>
          <div v-if="!isInTaskMode" class="header-actions">
            <button class="header-action-btn" @click="clearCurrentChat" aria-label="清空对话">
              <van-icon name="delete-o" size="18" color="#999"/>
            </button>
          </div>
        </div>
        <div class="agi-body" ref="bodyRef" role="list" @scroll="handleScroll" @click="handleBodyClick">
          <div v-if="displayMessages.length === 0" class="empty-state">
            <div class="empty-state-icon">
              <svg viewBox="0 0 24 24" width="48" height="48" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L14.09 8.26L20.18 8.63L15.54 12.54L16.91 18.77L12 15.4L7.09 18.77L8.46 12.54L3.82 8.63L9.91 8.26L12 2Z" fill="white"/>
              </svg>
            </div>
            <div class="empty-title">你好，我是探奇</div>
            <div class="empty-desc">可以问我关于实验、公式或科学现象的任何问题</div>
          </div>
          <div v-if="displayMessages.length > displayCount" class="load-more-tip">
            <van-loading v-if="isLoadingMore" size="16" color="#999"/>
            <span v-else>向上滚动加载更早消息</span>
          </div>
          <div v-for="msg in displayMessages" :key="msg.id" :class="['message-wrapper', msg.role === 'assistant' ? 'left' : 'right']" role="listitem">
            <div v-if="msg.role === 'assistant'" class="ai-avatar" :class="{ 'is-thinking': msg.status === 'streaming' }">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L14.09 8.26L20.18 8.63L15.54 12.54L16.91 18.77L12 15.4L7.09 18.77L8.46 12.54L3.82 8.63L9.91 8.26L12 2Z" fill="white"></path>
              </svg>
            </div>
            <div class="message-content-wrapper">
              <div class="bubble-container">
                <div v-if="shouldShowTime(msg.timestamp)" class="message-timestamp">
                  {{ formatRelativeTime(msg.timestamp) }}
                </div>
                <div class="message-bubble" :class="{ 'is-streaming': msg.status === 'streaming' }">
                  <template v-if="msg.status !== 'streaming'">
                    <div v-html="renderMarkdown(msg.content)"></div>
                    <div v-if="msg.role === 'user' && msg.status === 'error'" class="msg-error-actions">
                      <span class="error-text">发送失败</span>
                      <button class="retry-btn" @click="retryMessage(msg)" aria-label="重新发送消息">重试</button>
                    </div>
                  </template>
                  <template v-else>
                    <div v-html="renderStreamingContent(msg.content)"></div>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="agi-footer">
          <div class="input-container" :class="{ 'is-recording': isRecording, 'is-transcribing': isTranscribing }">
            <div class="voice-ripple-bg" v-if="isRecording">
              <span class="ripple"></span><span class="ripple"></span><span class="ripple"></span>
            </div>
            <van-field
              v-model="inputText"
              type="textarea"
              :autosize="{ maxHeight: 200, minHeight: 44 }"
              :readonly="isTranscribing"
              placeholder="询问关于实验、公式或科学现象的问题..."
              class="input-box"
              :class="{'is-streaming-input': isTranscribing}"
              @keydown.enter="handleEnterKey"
              aria-label="输入问题"
            />
            <button
              class="action-btn"
              :class="actionState"
              @click="handleActionClick"
              @mousedown="handlePointerDown"
              @mouseup="handlePointerUp"
              @mouseleave="handlePointerCancel"
              @touchstart.prevent="handlePointerDown"
              @touchend.prevent="handlePointerUp"
              @touchmove="handleTouchMove"
              :disabled="isProcessing || isTranscribing"
            >
              <div v-if="actionState === 'mic'" class="btn-content mic-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" fill="currentColor"/>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  <line x1="12" y1="19" x2="12" y2="23" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                  <line x1="8" y1="23" x2="16" y2="23" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <span class="recording-dot"></span>
              </div>
              <div v-else-if="actionState === 'recording'" class="btn-content voice-bars">
                <span class="bar b1"></span><span class="bar b2"></span><span class="bar b3"></span><span class="bar b4"></span><span class="bar b5"></span>
              </div>
              <div v-else-if="actionState === 'send'" class="btn-content send-icon">
                <van-icon name="guide-o"/>
              </div>
            </button>
          </div>
          <div class="ai-disclaimer">内容由AI生成，请仔细甄别</div>
        </div>
      </div>
    </transition>
  </div>
</template>
<script setup>
import {ref, computed, onMounted, nextTick, reactive, onBeforeUnmount, watch} from 'vue'
import {showToast, showConfirmDialog} from 'vant'
import {chatStream, asrStream} from '@/api/service.js'
import {useClipboard} from '@vueuse/core'
import MarkdownIt from 'markdown-it'
import texmath from 'markdown-it-texmath'
import katex from 'katex'
import DOMPurify from 'dompurify'
import Prism from 'prismjs'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'
import 'prismjs/themes/prism.css'
import 'katex/dist/katex.min.css'
import Mp3EncodeWorker from '../utils/mp3EncodeWorker.js?worker'
import 'markdown-it-texmath/css/texmath.css'
dayjs.extend(relativeTime)
dayjs.locale('zh-cn')
const props = defineProps({
  hideTrigger: {type: Boolean, default: false},
  roleSuffix: {type: String, required: true},
  overlay: {type: Boolean, default: true}
})
const emit = defineEmits(['submit-task', 'overlay-click'])
const {copy} = useClipboard()
const isOpen = ref(false) // 聊天面板是否展开
const inputText = ref('') // 输入框文本内容
const bodyRef = ref(null) // 聊天滚动区域DOM实例
const allMessages = ref([]) // 普通模式全部聊天消息数组
const displayCount = ref(10) // 消息分页单次展示条数
const isLoadingMore = ref(false) // 是否正在加载更早历史消息
const isProcessing = ref(false) // 是否正在请求AI流式回复
const abortController = ref(null) // 中断AI请求控制器
const isInTaskMode = ref(false) // 是否开启任务答题模式
const taskMessages = ref([]) // 任务模式专属聊天消息数组
const systemPromptRef = ref('') // 任务模式AI系统提示词
const taskContext = reactive({
  courseName: '',
  taskTitle: '',
  taskDesc: '',
  courseId: '',
  taskId: '',
  apiUrl: ''
})
const displayMessages = computed(() => {
  const source = isInTaskMode.value ? taskMessages.value : allMessages.value
  return source.slice(-displayCount.value)
})
const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  highlight: function (str, lang) {
    if (lang && Prism.languages[lang]) {
      try {
        return '<pre class="language-' + lang + '"><code>' + Prism.highlight(str, Prism.languages[lang], lang) + '</code></pre>'
      } catch (__) {}
    }
    return '<pre class="language-none"><code>' + md.utils.escapeHtml(str) + '</code></pre>'
  }
}).use(texmath, {engine: katex, delimiters: 'dollars', katexOptions: {macros: {'\\RR': '\\mathbb{R}'}}})
const isBlockUnclosed = (text) => {
  const codeBlocks = text.match(/```/g)
  const mathBlocks = text.match(/\$\$/g)
  return (codeBlocks && codeBlocks.length % 2 !== 0) || (mathBlocks && mathBlocks.length % 2 !== 0)
}
const injectCodeBlockUI = (htmlString) => {
  return htmlString.replace(/<pre class="language-(\w+)">/g, (match, lang) => {
    return `<div class="code-block-wrapper"><div class="code-block-header"><span class="code-lang">${lang}</span><button class="copy-code-btn" aria-label="复制代码" data-copy-code>复制</button></div><pre class="language-${lang}">`
  }).replace(/<\/pre>/g, '</pre></div>')
}
const renderMarkdown = (rawContent) => {
  let dirtyHtml = md.render(rawContent)
  dirtyHtml = injectCodeBlockUI(dirtyHtml)
  return DOMPurify.sanitize(dirtyHtml, {
    ADD_TAGS: ['iframe'],
    ADD_ATTR: ['allow', 'allowfullscreen', 'frameborder', 'scrolling', 'class', 'style', 'data-copy-code'],
    USE_PROFILES: {html: true, mathMl: true}
  })
}
const renderStreamingContent = (rawContent) => {
  if (isBlockUnclosed(rawContent)) {
    return DOMPurify.sanitize(`<div class="streaming-placeholder">${md.utils.escapeHtml(rawContent)}</div>`)
  }
  return renderMarkdown(rawContent)
}
const handleBodyClick = (e) => {
  const copyBtn = e.target.closest('[data-copy-code]')
  if (copyBtn) {
    const wrapper = copyBtn.closest('.code-block-wrapper')
    const codeEl = wrapper?.querySelector('code')
    if (codeEl) {
      copy(codeEl.textContent)
      showToast({message: '已复制', position: 'bottom'})
    }
  }
}
const formatRelativeTime = (timestamp) => dayjs(timestamp).fromNow()
const shouldShowTime = (currentTimestamp) => {
  const msgs = isInTaskMode.value ? taskMessages.value : allMessages.value
  const idx = msgs.findIndex((m) => m.timestamp === currentTimestamp)
  if (idx <= 0) return true
  return currentTimestamp - msgs[idx - 1].timestamp > 5 * 60 * 1000
}
const togglePanel = (forceState) => {
  isOpen.value = typeof forceState === 'boolean' ? forceState : !isOpen.value
}
const handleOverlayClick = () => {
  togglePanel(false)
  emit('overlay-click')
}
const scrollToBottom = async () => {
  await nextTick()
  if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight
}
watch(isOpen, (newVal) => {
  if (newVal) {
    nextTick(() => { scrollToBottom() })
  }
})
const handleScroll = () => {
  if (!bodyRef.value || isLoadingMore.value) return
  const {scrollTop} = bodyRef.value
  const source = isInTaskMode.value ? taskMessages.value : allMessages.value
  if (scrollTop <= 0 && source.length > displayCount.value) {
    isLoadingMore.value = true
    const firstMsgEl = bodyRef.value.querySelector('.message-wrapper')
    const prevHeight = firstMsgEl ? firstMsgEl.offsetTop + firstMsgEl.offsetHeight : 0
    displayCount.value = Math.min(displayCount.value + 10, source.length)
    nextTick(() => {
      if (bodyRef.value) {
        const newFirstMsgEl = bodyRef.value.querySelector('.message-wrapper')
        const newHeight = newFirstMsgEl ? newFirstMsgEl.offsetTop + newFirstMsgEl.offsetHeight : 0
        bodyRef.value.scrollTop = newHeight - prevHeight
        isLoadingMore.value = false
      }
    })
  }
}
const saveHistory = () => {
  if (isInTaskMode.value) return
  localStorage.setItem('gai_chat_history', JSON.stringify(allMessages.value.slice(-30)))
}
const loadHistory = () => {
  const history = localStorage.getItem('gai_chat_history')
  if (history) {
    try {
      allMessages.value = JSON.parse(history).map((msg) => ({...msg, status: msg.status || 'done'}))
    } catch (e) {
      console.error('解析历史记录失败', e)
    }
  }
}
const handleEnterKey = (e) => {
  if (e.shiftKey) return
  e.preventDefault() // 阻止浏览器默认换行行为
  sendMessage()
}
const handleStreamResponse = async (messagesPayload, userMsg, aiMsg, targetArray) => {
  if (!props.roleSuffix || !props.roleSuffix.trim()) {
    throw new Error('[GAI Component Fatal] 必须通过 roleSuffix 属性传递流式请求的角色路径后缀')
  }
  isProcessing.value = true
  if (userMsg) userMsg.status = 'sending'

  let isMsgPushed = false
  abortController.value = new AbortController()
  const finalUrl = (isInTaskMode.value && taskContext.apiUrl) ? taskContext.apiUrl : `/service/chat/stream/${props.roleSuffix}`

  let renderBuffer = ''
  let flushTimer = null
  const startFlush = () => {
    if (flushTimer) return
    flushTimer = setInterval(() => {
      if (renderBuffer.length > 0) {
        const chunkSize = Math.min(renderBuffer.length, Math.max(1, Math.ceil(renderBuffer.length / 3)))
        const chunk = renderBuffer.substring(0, chunkSize)
        renderBuffer = renderBuffer.substring(chunkSize)
        aiMsg.content += chunk
        scrollToBottom()
      }
    }, 30)
  }
  const stopFlush = () => {
    if (flushTimer) {
      clearInterval(flushTimer)
      flushTimer = null
    }
    if (renderBuffer.length > 0) {
      aiMsg.content += renderBuffer
      renderBuffer = ''
      scrollToBottom()
    }
  }
  try {
    await chatStream({
      url: finalUrl,
      messages: messagesPayload,
      signal: abortController.value.signal
    }, {
      onToken: (content) => {
        if (!isMsgPushed) {
          targetArray.push(aiMsg)
          isMsgPushed = true
          if (userMsg) userMsg.status = 'done'
          startFlush()
        }
        renderBuffer += content
      },
      onDone: () => {
        stopFlush()
        aiMsg.status = 'done'
        isProcessing.value = false
        saveHistory()
      },
      onError: (msg) => {
        stopFlush()
        showToast(msg)
        if (isMsgPushed) aiMsg.status = 'error'
        else if (userMsg) userMsg.status = 'error'
        isProcessing.value = false
      }
    })
  } catch (error) {
    stopFlush()
    if (error.name !== 'AbortError') console.error('流式请求异常:', error)
  }
}
const sendMessage = async (eventOrText) => {
  const isProgrammatic = typeof eventOrText === 'string'
  const text = isProgrammatic ? eventOrText : inputText.value.trim()
  if (!text || isProcessing.value) return
  const targetArray = isInTaskMode.value ? taskMessages.value : allMessages.value
  const userMsg = reactive({
    id: Date.now().toString(),
    role: 'user',
    content: text,
    timestamp: Date.now(),
    status: 'done'
  })
  targetArray.push(userMsg)
  if (!isProgrammatic) inputText.value = ''
  saveHistory()
  scrollToBottom()
  const aiMsg = reactive({
    id: (Date.now() + 1).toString(),
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    status: 'streaming'
  })
  let messagesPayload = targetArray.map((m) => ({role: m.role, content: m.content}))
  if (isInTaskMode.value && systemPromptRef.value) {
    messagesPayload.unshift({role: 'user', content: systemPromptRef.value})
  }
  await handleStreamResponse(messagesPayload, userMsg, aiMsg, targetArray)
}
const retryMessage = async (userMsg) => {
  const targetArray = isInTaskMode.value ? taskMessages.value : allMessages.value
  const userIndex = targetArray.findIndex((m) => m.id === userMsg.id)
  if (userIndex !== -1 && userIndex < targetArray.length - 1) {
    const nextMsg = targetArray[userIndex + 1]
    if (nextMsg.role === 'assistant') targetArray.splice(userIndex + 1, 1)
  }
  const aiMsg = reactive({
    id: (Date.now() + 1).toString(),
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    status: 'streaming'
  })
  let messagesPayload = targetArray.map((m) => ({role: m.role, content: m.content}))
  if (isInTaskMode.value && systemPromptRef.value) {
    messagesPayload.unshift({role: 'user', content: systemPromptRef.value})
  }
  await handleStreamResponse(messagesPayload, userMsg, aiMsg, targetArray)
}
const sendSilentMessage = async (text) => {
  if (!text || isProcessing.value) return
  scrollToBottom()
  let messagesPayload = allMessages.value.map((m) => ({role: m.role, content: m.content}))
  if (messagesPayload.length === 0) messagesPayload.push({role: 'user', content: '开始'})
  messagesPayload.push({role: 'user', content: text})
  const aiMsg = reactive({
    id: (Date.now() + 1).toString(),
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    status: 'streaming'
  })
  await handleStreamResponse(messagesPayload, null, aiMsg, allMessages.value)
}
const handleClearHistory = async () => {
  try {
    await showConfirmDialog({ title: '确认清空', message: '是否清空当前对话记录？' })
    allMessages.value = []
    localStorage.removeItem('gai_chat_history')
  } catch (e) {}
}
const clearCurrentChat = () => {
  if (isInTaskMode.value) taskMessages.value = []
  else allMessages.value = []
}
const startTaskMode = async ({courseName, taskTitle, taskDesc, promptText, courseId, taskId, apiUrl}) => {
  Object.assign(taskContext, {courseName, taskTitle, taskDesc, courseId, taskId, apiUrl})
  taskMessages.value = []
  systemPromptRef.value = promptText
  isInTaskMode.value = true
  togglePanel(true)
  await nextTick()
  const initPayload = [
    {role: 'user', content: promptText},
    {role: 'user', content: '开始'}
  ]
  const aiMsg = reactive({
    id: (Date.now() + 1).toString(),
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    status: 'streaming'
  })
  await handleStreamResponse(initPayload, null, aiMsg, taskMessages.value)
}
const handleSubmitTask = () => {
  if (taskMessages.value.length === 0) return
  const hasValidAiReply = taskMessages.value.some(m => m.role === 'assistant' && m.content.trim() !== '')
  if (!hasValidAiReply) {
    showToast({message: '请先与AI进行至少一轮交流', type: 'fail', position: 'bottom'})
    return
  }
  const realChatHistory = taskMessages.value.map(m => ({role: m.role, content: m.content}))
  emit('submit-task', {taskId: taskContext.taskId, courseId: taskContext.courseId, messages: realChatHistory})
}
const exitTaskMode = () => {
  if (abortController.value) abortController.value.abort()
  isInTaskMode.value = false
  taskMessages.value = []
  systemPromptRef.value = ''
  Object.keys(taskContext).forEach(key => taskContext[key] = '')
  isProcessing.value = false
  inputText.value = ''
}
// ==========================================
// === 语音输入与录音状态管理 (修复版) ===
// ==========================================
const isRecording = ref(false)
const isTranscribing = ref(false)
const isRecordingCancelled = ref(false)
const touchStartPos = reactive({x: 0, y: 0})
// 录音相关上下文
let audioContext = null
let mediaStream = null
let recorderNode = null
let mp3Worker = null
let maxRecordTimer = null
let asrAbortController = null
const actionState = computed(() => {
  if (isRecording.value) return 'recording'
  if (inputText.value.trim()) return 'send'
  return 'mic'
})
const RECORDER_WORKLET_CODE = `
class RecorderProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._isRecording = false;
    // 必须在构造函数中监听 port 消息
    this.port.onmessage = (event) => {
      if (event.data.type === 'start') {
        this._isRecording = true;
      } else if (event.data.type === 'stop') {
        this._isRecording = false;
      }
    };
  }
  process(inputs) {
    const input = inputs[0][0];
    if (!this._isRecording || !input || input.length === 0) {
      return true;
    }
    const samples = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      let s = Math.max(-1, Math.min(1, input[i]));
      samples[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    this.port.postMessage(
      { type: 'pcm', buffer: samples.buffer },
      [samples.buffer]
    );
    return true;
  }
}
registerProcessor('recorder-processor', RecorderProcessor);
`
const handleAsrRequest = async (file) => {
  isTranscribing.value = true
  asrAbortController = new AbortController()

  const formData = new FormData()
  formData.append('file', file)

  try {
    await asrStream({
      formData: formData,
      signal: asrAbortController.signal
    }, {
      onToken: (content) => {
        inputText.value += content
      },
      onDone: () => {
        isTranscribing.value = false
      },
      onError: (msg) => {
        isTranscribing.value = false
        showToast(msg || '语音识别失败')
      }
    })
  } catch (error) {
    if (error.name !== 'AbortError') {
      console.error('ASR 请求异常:', error)
    }
    isTranscribing.value = false
  }
}
const handlePointerDown = async (e) => {
  if (actionState.value !== 'mic' || isProcessing.value) return
  isRecordingCancelled.value = false

  // 1. 环境前置检查
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showToast('当前环境不支持麦克风，请确保在 HTTPS 或 localhost 下运行')
    return
  }
  if (!window.AudioWorkletNode) {
    showToast('您的浏览器版本过低，不支持音频录制功能，请升级浏览器')
    return
  }
  try {
    // 2. 获取麦克风权限
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioContext = new (window.AudioContext || window.webkitAudioContext)()
    await audioContext.resume()
    // 3. 使用 Blob URL 加载 Worklet，绕过 Vite/Webpack 的 HMR 注入
    const workletBlob = new Blob([RECORDER_WORKLET_CODE], { type: 'application/javascript; utf-8' })
    const workletUrl = URL.createObjectURL(workletBlob)
    await audioContext.audioWorklet.addModule(workletUrl)
    URL.revokeObjectURL(workletUrl) // 加载后释放 URL
    // 4. 创建节点链路
    const source = audioContext.createMediaStreamSource(mediaStream)
    recorderNode = new AudioWorkletNode(audioContext, 'recorder-processor')
    // 5. 初始化 MP3 编码 Worker (修复1: 路径修正 & 修复4: 终止旧Worker)
    if (mp3Worker) {
      mp3Worker.terminate()
    }
    mp3Worker = new Mp3EncodeWorker()

    mp3Worker.postMessage({
      type: 'init',
      sampleRate: audioContext.sampleRate,
      bitRate: 128
    })
    // 6. 监听 Worker 返回的最终 MP3 Blob
    mp3Worker.onmessage = (event) => {
      if (event.data.type === 'mp3') {
        const mp3Blob = event.data.blob
        const file = new File([mp3Blob], 'recording.mp3', { type: 'audio/mp3' })
        handleAsrRequest(file)
      }
    }
    // 7. 监听 Worklet 采集的 PCM 数据并转发给 Worker
    recorderNode.port.onmessage = (event) => {
      if (event.data.type === 'pcm' && mp3Worker) {
        mp3Worker.postMessage({ type: 'pcm', buffer: event.data.buffer }, [event.data.buffer])
      }
    }
    // 8. 连接音频图
    source.connect(recorderNode)
    recorderNode.connect(audioContext.destination)
    // 9. 通知 Worklet 开始录音
    recorderNode.port.postMessage({ type: 'start' })
    isRecording.value = true
    // 10. 5 分钟最长录音限制
    maxRecordTimer = setTimeout(() => {
      handlePointerUp()
      showToast('已达到最长录音时间限制（5分钟）')
    }, 300000)
    if (e.touches) {
      touchStartPos.x = e.touches[0].clientX
      touchStartPos.y = e.touches[0].clientY
    }
  } catch (error) {
    console.error('麦克风启动失败:', error)

    let errorMessage = '无法访问麦克风'
    if (error instanceof DOMException) {
      switch (error.name) {
        case 'NotAllowedError':
          errorMessage = '麦克风权限被拒绝，请在浏览器设置中允许本站访问'
          break
        case 'NotFoundError':
          errorMessage = '未检测到麦克风设备'
          break
        case 'NotReadableError':
          errorMessage = '麦克风被其他程序占用，请检查'
          break
        case 'SecurityError':
          errorMessage = '安全限制，请确保在 HTTPS 环境下访问'
          break
        default:
          errorMessage = `麦克风错误: ${error.message}`
      }
    }
    showToast(errorMessage)
    cleanUpRecordingResources()
  }
}
const cleanUpRecordingResources = () => {
  if (maxRecordTimer) {
    clearTimeout(maxRecordTimer)
    maxRecordTimer = null
  }
  if (recorderNode) {
    recorderNode.disconnect()
    recorderNode = null
  }
  if (audioContext) {
    audioContext.close()
    audioContext = null
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop())
    mediaStream = null
  }
  isRecording.value = false
}
const handlePointerUp = () => {
  if (!isRecording.value) return

  // 1. 先停止录音节点和通知生成
  if (!isRecordingCancelled.value) {
    if (recorderNode) {
      recorderNode.port.postMessage({ type: 'stop' })
    }
    if (mp3Worker) {
      mp3Worker.postMessage({ type: 'stop' })
    }
  } else {
    // 如果是取消状态，直接终止 Worker 丢弃录音
    if (mp3Worker) {
      mp3Worker.terminate()
      mp3Worker = null
    }
  }
  // 2. 最后清理音频资源
  cleanUpRecordingResources()
}
const handleTouchMove = (e) => {
  if (!isRecording.value || isRecordingCancelled.value) return
  const touch = e.touches[0]
  const deltaY = Math.abs(touch.clientY - touchStartPos.y)
  const deltaX = Math.abs(touch.clientX - touchStartPos.x)
  if (deltaX > 40 || deltaY > 40) {
    isRecordingCancelled.value = true
  }
}
const handlePointerCancel = () => {
  if (isRecording.value) {
    isRecordingCancelled.value = true
    handlePointerUp()
  }
}
const handleActionClick = () => {
  if (actionState.value === 'send') {
    sendMessage()
  }
}
onMounted(() => {
  loadHistory()
})
onBeforeUnmount(() => {
  if (abortController.value) abortController.value.abort()
  if (asrAbortController) asrAbortController.abort()
  cleanUpRecordingResources()
  if (mp3Worker) mp3Worker.terminate()
})
defineExpose({
  isOpen,
  togglePanel,
  triggerMessage: (text) => sendMessage(text),
  sendSilentMessage,
  isInTaskMode,
  startTaskMode,
  exitTaskMode,
  handleSubmitTask,
  allMessages
})
</script>
<style scoped src="../styles/components/GAI.css"></style>