<template>
  <div class="student-study-page page-fade-enter" :class="{ 'gai-split-active': isGAIMode }">
    <div class="main-body" :class="{ 'gai-split-active': isGAIMode }">
      <!-- 移除 v-show，将缩小状态与 isGAIMode 绑定实现联动 -->
      <div class="area-header" :class="{ 'is-completed': isGAIMode }">
        <div class="back-btn-wrapper" :class="{ 'is-completed': isGAIMode }" @click="goBack">
          <div class="back-btn" :class="{ 'is-completed': isGAIMode }">
            <van-icon name="arrow-left" :size="isGAIMode ? 16 : 24" color="#333333"/>
          </div>
        </div>
        <div class="task-context">
          <div class="chapter-name" :class="{ 'is-completed': isGAIMode }">{{ chapterName }}</div>
          <div class="task-title-row">
            <div class="status-icon" :class="isCompleted ? 'is-done' : 'is-pending'">
              <van-icon v-if="isCompleted" name="success" color="#FFFFFF" size="14"/>
              <van-icon v-else name="ellipsis" color="#FFFFFF" size="14"/>
            </div>
            <div class="task-name">{{ taskName }}</div>
          </div>
        </div>
      </div>
      <div class="area-content" :class="{ 'gai-split-active': isGAIMode }">
        <div v-if="isLoading" class="dots-loading-wrap">
          <div class="dots-loading">
            <span v-for="i in 5" :key="i" class="dot"></span>
          </div>
          <div class="dots-loading-text">正在加载，请稍候...</div>
        </div>
        <div v-else-if="loadError" class="load-error-wrap">
          <van-icon name="warning-o" size="48" color="#999999"/>
          <div class="load-error-text">{{ loadError }}</div>
          <van-button type="primary" size="small" round @click="retryLoad">
            重新加载
          </van-button>
        </div>
        <div v-else-if="resourceType === 'video'" class="video-container">
          <video
              ref="videoRef"
              class="custom-video-player"
              :src="resourceUrl"
              controls
              controlslist="nodownload"
              preload="auto"
              @loadeddata="handleVideoReady"
              @error="handleVideoError"
              @ended="handleResourceComplete"
          >
            您的浏览器不支持视频播放。
          </video>
        </div>
        <div v-else-if="resourceType === 'pdf'" class="pdf-container blur-vertical" ref="pdfScrollRef"
             @scroll="handlePdfScroll">
          <div id="pdf-render-container" style="width: 100%;"></div>
        </div>
      </div>
      <div class="area-feedback" v-show="isJustCompleted" :class="{ 'is-hiding': isFeedbackHiding }">
        <div class="feedback-inner">
          <div class="feedback-prompt" :class="{ 'is-visible': showPrompt }">
            你觉得本节内容难度如何?
          </div>
          <div class="feedback-buttons" :class="{ 'is-visible': showButtons }">
            <button
                v-for="(btn, index) in difficultyOptions"
                :key="index"
                class="diff-btn"
                :class="{ 'is-selected': selectedDifficulty === btn.value }"
                :disabled="feedbackSubmitted"
                @click="submitFeedback(btn.value)"
            >
              {{ btn.label }}
            </button>
          </div>
        </div>
      </div>
    </div>
<GAI ref="gaiRef" roleSuffix="student" :overlay="!isGAIMode"/>
  </div>
</template>

<script setup>
import {ref, onMounted, onBeforeUnmount, nextTick, watch} from 'vue'
import {useRouter, useRoute, onBeforeRouteLeave} from 'vue-router'
import {showToast, showDialog} from 'vant'
import GAI from '@/components/GAI.vue'
import {complete_section, submit_feedback, get_section_detail, report_study_duration} from '@/api/course.js'
import * as pdfjsLib from 'pdfjs-dist'

pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'

const router = useRouter()
const route = useRoute()
const courseId = route.query.courseId
const sectionId = route.query.sectionId

const RESOURCE_BASE_URL = import.meta.env.VITE_RESOURCE_BASE_URL || ''

/**
 * 拼接完整的资源访问地址
 * @param {string} rawUrl - 接口返回的原始相对路径或完整URL
 * @returns {string} 拼接后的可访问URL
 */
const resolveResourceUrl = (rawUrl) => {
  if (!rawUrl) return ''
  const trimmed = rawUrl.trim()
  if (!trimmed) return ''
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) return trimmed
  const base = RESOURCE_BASE_URL.replace(/\/+$/, '')
  if (trimmed.startsWith('/')) return base + trimmed
  return base + '/' + trimmed
}

const chapterName = ref('')
const taskName = ref('')
const isCompleted = ref(false)
const resourceType = ref('')
const resourceUrl = ref('')
const isLoading = ref(true)
const loadError = ref('')
const completedMarkSent = ref(false)
const isJustCompleted = ref(false)
const showPrompt = ref(false)
const showButtons = ref(false)
const isGAIMode = ref(false)
const isFeedbackHiding = ref(false)
const gaiRef = ref(null)

const difficultyOptions = [
  {label: '理解较难', value: 1},
  {label: '大部分难', value: 2},
  {label: '部分难', value: 3},
  {label: '较简单', value: 4},
  {label: '完全理解', value: 5},
]

const selectedDifficulty = ref(null)
const feedbackSubmitted = ref(false)
const pdfScrollRef = ref(null)
const videoRef = ref(null)

let studyStartTime = null
let isStudying = false
const MIN_REPORT_SECONDS = 2

const startTimer = () => {
  if (isStudying) return
  isStudying = true
  studyStartTime = Date.now()
}

const pauseAndReport = () => {
  if (!isStudying || !studyStartTime) return
  isStudying = false
  const elapsedSec = Math.floor((Date.now() - studyStartTime) / 1000)
  studyStartTime = null
  if (elapsedSec < MIN_REPORT_SECONDS) return
  report_study_duration(courseId, elapsedSec).catch(() => {
  })
}

const handleVisibilityChange = () => {
  if (document.hidden) {
    pauseAndReport()
  } else {
    if (!isLoading.value) startTimer()
  }
}

/**
 * 提取 PDF 全文文本用于 AI 上下文
 * @param {string} url - PDF文件URL
 * @returns {Promise<string>} 提取的纯文本内容
 */
const extractPdfText = async (url) => {
  try {
    const loadingTask = pdfjsLib.getDocument(url)
    const pdf = await loadingTask.promise
    let fullText = ''
    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i)
      const textContent = await page.getTextContent()
      const pageText = textContent.items.map(item => item.str).join(' ')
      fullText += pageText + '\n'
    }
    return fullText.trim()
  } catch (error) {
    console.error('PDF文本提取失败:', error)
    return ''
  }
}

/**
 * 渲染 PDF 到指定容器
 * @param {string} url - PDF文件URL
 */
const renderPdfToContainer = async (url) => {
  const container = document.getElementById('pdf-render-container')
  if (!container) return
  container.innerHTML = ''
  try {
    const loadingTask = pdfjsLib.getDocument(url)
    const pdf = await loadingTask.promise
    const containerWidth = container.clientWidth - 48
    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i)
      const originalViewport = page.getViewport({scale: 1})
      const desiredScale = containerWidth / originalViewport.width
      const viewport = page.getViewport({scale: desiredScale})
      const canvas = document.createElement('canvas')
      const context = canvas.getContext('2d')
      const dpr = window.devicePixelRatio || 1
      canvas.width = Math.floor(viewport.width * dpr)
      canvas.height = Math.floor(viewport.height * dpr)
      canvas.style.width = Math.floor(viewport.width) + 'px'
      canvas.style.height = Math.floor(viewport.height) + 'px'
      canvas.style.marginBottom = '16px'
      canvas.style.display = 'block'
      context.scale(dpr, dpr)
      container.appendChild(canvas)
      await page.render({canvasContext: context, viewport: viewport}).promise
    }
  } catch (error) {
    console.error('PDF渲染失败:', error)
    loadError.value = 'PDF 文件加载失败，请检查网络连接后重试'
  }
}

const fetchSectionDetail = async () => {
  try {
    const res = await get_section_detail(courseId, sectionId)
    const d = res.data
    chapterName.value = d.chapter_name || '默认章节'
    taskName.value = d.section_title || d.task_name || d.title || '未命名任务'
    const rawType = d.resource_type || d.section_type || d.type || d.media_type || ''
    const rawUrl = d.resource_url || d.resource_path || d.file_url || d.url || d.file_path || d.video_url || ''
    resourceType.value = rawType
    resourceUrl.value = resolveResourceUrl(rawUrl)
    isCompleted.value = !!d.is_completed
    completedMarkSent.value = !!d.is_completed
    isLoading.value = false
    if (!resourceType.value || !resourceUrl.value) {
      console.warn('资源信息不完整:', {type: rawType, url: rawUrl, resolved: resourceUrl.value})
      loadError.value = '未获取到学习资源，请联系老师'
      return
    }
    await nextTick()
    if (resourceType.value === 'pdf') {
      await renderPdfToContainer(resourceUrl.value)
    }
    startTimer()
  } catch (error) {
    console.error('获取小节详情失败:', error)
    isLoading.value = false
    loadError.value = '加载失败，请检查网络后重试'
  }
}

const retryLoad = () => {
  loadError.value = ''
  isLoading.value = true
  fetchSectionDetail()
}

const handleVideoReady = () => {
  console.log('视频加载成功:', resourceUrl.value)
}

const handleVideoError = (e) => {
  console.error('视频加载失败:', e)
  loadError.value = '视频加载失败，请检查网络连接后重试'
}

const goBack = () => {
  if (isJustCompleted.value && !feedbackSubmitted.value) {
    showDialog({
      title: '提示',
      message: '您需要完成章节评价',
      showCancelButton: false,
      confirmButtonText: '我知道了'
    }).catch(() => {
    })
    return
  }
  router.back()
}

onBeforeRouteLeave((to, from, next) => {
  pauseAndReport()
  if (isJustCompleted.value && !feedbackSubmitted.value) {
    showDialog({
      title: '提示',
      message: '您需要完成章节评价',
      showCancelButton: false,
      confirmButtonText: '我知道了'
    }).then(() => next(false)).catch(() => next(false))
  } else {
    next()
  }
})

const handleResourceComplete = async () => {
  if (completedMarkSent.value) return
  completedMarkSent.value = true
  isCompleted.value = true
  isJustCompleted.value = true
  setTimeout(() => {
    showPrompt.value = true
  }, 100)
  setTimeout(() => {
    showButtons.value = true
  }, 350)
}

const handlePdfScroll = (e) => {
  if (completedMarkSent.value) return
  const {scrollTop, clientHeight, scrollHeight} = e.target
  if (scrollHeight - scrollTop - clientHeight <= 50) {
    handleResourceComplete()
  }
}

const submitFeedback = async (value) => {
  if (feedbackSubmitted.value) return
  selectedDifficulty.value = value
  feedbackSubmitted.value = true
  await complete_section(courseId, sectionId)
  await submit_feedback(courseId, sectionId, value)
  showToast({
    message: '反馈成功，正在开启智能助教...',
    position: 'bottom'
  })
  isFeedbackHiding.value = true
  setTimeout(async () => {
    // isGAIMode 赋值时，将同时触发 GAI 面板弹出和 area-header 缩小
    isGAIMode.value = true
    await nextTick()
    setTimeout(() => {
      gaiRef.value?.togglePanel(true)
      const buildContextAndSend = async () => {
        let contextText = ''
        if (resourceType.value === 'video') {
          contextText = `当前学习视频的小节标题为：${taskName.value}`
        } else if (resourceType.value === 'pdf') {
          showToast({
            message: '正在解析文档内容，请稍候...',
            position: 'bottom',
            duration: 2000
          })
          contextText = await extractPdfText(resourceUrl.value)
          if (!contextText) contextText = '文档内容解析失败'
        }
        const silentCmd = `这是系统发送的信息：学生刚刚完成了本小节的学习并提交了反馈。以下是本小节的学习资料内容上下文，请在后续对话中基于此内容为学生答疑解惑：\n${contextText}`
        gaiRef.value?.sendSilentMessage(silentCmd)
      }
      buildContextAndSend()
    }, 300)
  }, 450)
}

watch(() => gaiRef.value?.isOpen, (newVal) => {
  if (newVal === false && isGAIMode.value === true) {
    isGAIMode.value = false
  }
})

const checkPdfSingleScreenComplete = async () => {
  if (resourceType.value !== 'pdf') return
  if (completedMarkSent.value) return
  await nextTick()
  if (!pdfScrollRef.value) return
  const {clientHeight, scrollHeight} = pdfScrollRef.value
  if (scrollHeight <= clientHeight) {
    handleResourceComplete()
  }
}

onMounted(async () => {
  document.addEventListener('visibilitychange', handleVisibilityChange)
  await fetchSectionDetail()
  await checkPdfSingleScreenComplete()
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  pauseAndReport()
})
</script>

<style scoped src="../../styles/views/student/StudentStudy.css"></style>
