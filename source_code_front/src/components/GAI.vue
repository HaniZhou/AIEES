<template>
  <div class="agi-container" :class="{ 'is-task-mode': isInTaskMode }">
    <!-- 任务模式遮罩层 -->
    <div v-if="isOpen && isInTaskMode" class="agi-overlay" @click="togglePanel(false)"></div>

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
            <button class="header-action-btn" @click="handleClearHistory" aria-label="清空对话">
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
          <div class="input-container">
            <van-field v-model="inputText" type="textarea" :autosize="{ maxHeight: 200, minHeight: 44 }" placeholder="询问关于实验、公式或科学现象的问题..." class="input-box" @keydown.enter="handleEnterKey" aria-label="输入问题"/>
            <button class="send-btn" :disabled="!inputText.trim() || isProcessing" @click="sendMessage" :aria-label="isProcessing ? '正在生成中' : '发送消息'" :aria-disabled="isProcessing">
              <van-icon name="guide-o"/>
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
import {chatStream} from '@/api/services'
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
import 'markdown-it-texmath/css/texmath.css'
dayjs.extend(relativeTime)
dayjs.locale('zh-cn')
const props = defineProps({
  hideTrigger: {type: Boolean, default: false},
  roleSuffix: {type: String, required: true}
})
const emit = defineEmits(['submit-task'])
const {copy} = useClipboard()
const isOpen = ref(false)
const inputText = ref('')
const bodyRef = ref(null)
const allMessages = ref([])
const displayCount = ref(10)
const isLoadingMore = ref(false)
const isProcessing = ref(false)
const abortController = ref(null)
const isInTaskMode = ref(false)
const taskMessages = ref([])
const systemPromptRef = ref('')
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
      } catch (__) {
      }
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
  return DOMPurify.sanitize(dirtyHtml, {ADD_TAGS: ['iframe'], ADD_ATTR: ['allow', 'allowfullscreen', 'frameborder', 'scrolling', 'class', 'style', 'data-copy-code'], USE_PROFILES: {html: true, mathMl: true}})
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
      copy(codeEl.textContent);
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
const scrollToBottom = async () => {
  await nextTick()
  if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight
}
watch(isOpen, (newVal) => {
  if (newVal) {
    nextTick(() => {
      scrollToBottom()
    })
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
  if (e.shiftKey) return;
  e.preventDefault();
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
  const finalUrl = (isInTaskMode.value && taskContext.apiUrl) ? taskContext.apiUrl : `/services/chat/stream/${props.roleSuffix}`
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
        aiMsg.status = 'done';
        isProcessing.value = false;
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
  const userMsg = reactive({id: Date.now().toString(), role: 'user', content: text, timestamp: Date.now(), status: 'done'})
  targetArray.push(userMsg)
  if (!isProgrammatic) inputText.value = ''
  saveHistory();
  scrollToBottom()
  const aiMsg = reactive({id: (Date.now() + 1).toString(), role: 'assistant', content: '', timestamp: Date.now(), status: 'streaming'})
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
  const aiMsg = reactive({id: (Date.now() + 1).toString(), role: 'assistant', content: '', timestamp: Date.now(), status: 'streaming'})
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
  const aiMsg = reactive({id: (Date.now() + 1).toString(), role: 'assistant', content: '', timestamp: Date.now(), status: 'streaming'})
  await handleStreamResponse(messagesPayload, null, aiMsg, allMessages.value)
}
const handleClearHistory = async () => {
  try {
    await showConfirmDialog({
      title: '确认清空',
      message: '是否清空当前对话记录？',
    })
    allMessages.value = []
    localStorage.removeItem('gai_chat_history')
  } catch (e) {
  }
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
  const aiMsg = reactive({id: (Date.now() + 1).toString(), role: 'assistant', content: '', timestamp: Date.now(), status: 'streaming'})
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
onMounted(() => {
  loadHistory()
})
onBeforeUnmount(() => {
  if (abortController.value) abortController.value.abort()
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