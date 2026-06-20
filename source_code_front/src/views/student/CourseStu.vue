<template>
  <div class="course-stu-page page-fade-enter">
    <!-- 1. 顶部导航栏 -->
    <AppHeader role="student" :userName="studentName || '学生'"/>
    <!-- 2. 页面主体：左右两栏布局 -->
    <div class="main-body">
      <!-- ================= 左侧导航区 (25%) ================= -->
      <aside class="left-panel">
        <div class="left-panel-inner">
          <div class="course-info-card">
            <img :src="courseInfo.cover" alt="课程封面" class="course-cover"/>
            <h2 class="course-name">{{ courseInfo.name }}</h2>
            <p class="course-teacher">{{ courseInfo.teacher }}</p>
          </div>
          <div class="view-switcher-col">
            <div class="switch-tab-row" :class="{ active: activeLeftTab === 'chapter' }" @click="switchTab('chapter')">
              <span>章节</span>
              <div class="active-indicator" v-if="activeLeftTab === 'chapter'"></div>
            </div>
            <div class="switch-tab-row" :class="{ active: activeLeftTab === 'task' }" @click="switchTab('task')">
              <span>任务</span>
              <div class="active-indicator" v-if="activeLeftTab === 'task'"></div>
            </div>
            <div class="switch-tab-row" :class="{ active: activeLeftTab === 'gai-task' }"
                 @click="switchTab('gai-task')">
              <span>人机交互任务</span>
              <div class="active-indicator" v-if="activeLeftTab === 'gai-task'"></div>
            </div>
          </div>
        </div>
      </aside>
      <!-- ================= 右侧内容区 (75%) ================= -->
      <main class="right-panel">
        <div class="right-top-content blur-vertical">
          <!-- 视图一：章节学习 -->
          <div v-if="activeLeftTab === 'chapter'" class="chapter-view">
            <div v-for="(chapter, cIndex) in chapterList" :key="chapter.id" class="chapter-group">
              <div class="chapter-header" @click="toggleChapter(cIndex)">
                <div class="header-left">
                  <span class="chapter-title">{{ chapter.title }}</span>
                </div>
                <div class="header-right">
                  <van-icon name="arrow" class="arrow-icon" :class="{ 'is-expanded': chapter.expanded }"/>
                </div>
              </div>
              <div class="sub-task-list" :class="{ 'is-expanded': chapter.expanded }">
                <div v-for="(task, tIndex) in chapter.subTasks" :key="task.id" class="sub-task-item"
                     @click="handleSubTaskClick(task)">
                  <div class="sub-task-item-left">
                    <div class="status-icon" :class="task.isCompleted ? 'status-done' : 'status-pending'">
                      <van-icon v-if="task.isCompleted" name="success" color="#FFFFFF" size="12"/>
                      <span v-else>{{ tIndex + 1 }}</span>
                    </div>
                    <span class="sub-task-name">{{ task.title }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <!-- 视图二：普通任务列表 -->
          <div v-if="activeLeftTab === 'task'" class="task-view">
            <div v-for="t in taskList" :key="t.id" class="task-item-wrapper">
              <div class="task-card" @click="handleTaskClick(t)">
                <div class="task-col-left">
                  <van-icon name="edit" class="task-type-icon"/>
                </div>
                <div class="task-col-middle"><span class="task-name">{{ t.title }}</span></div>
                <div class="task-col-right">
                  <span class="status-text" v-if="t.isCompleted">已提交</span>
                  <span class="status-text expired-text" v-else-if="t.isExpired">已经截止</span>
                  <span class="deadline-text" v-else>{{ toLocalTime(t.deadline) }}</span>
                  <van-icon name="arrow" class="arrow-icon ml-12"/>
                </div>
              </div>
            </div>
          </div>
          <!-- 视图三：人机交互任务 -->
          <div v-if="activeLeftTab === 'gai-task'" class="task-view">
            <div v-for="gt in gaiTaskList" :key="gt.id" class="gai-task-wrapper"
                 :class="{ 'is-active': currentActiveTaskId === gt.id }">
              <!-- 列表卡片  -->
              <div class="task-card" @click="handleToggleGaiPanel(gt)">
                <div class="task-col-left">
                  <van-icon name="chat-o" class="task-type-icon"/>
                </div>
                <div class="task-col-middle">
                  <span class="task-name">{{ gt.title }}</span>
                </div>
                <div class="task-col-right">
                  <span class="status-text" v-if="gt.isCompleted">已提交</span>
                  <span class="status-text expired-text" v-else-if="gt.isExpired">已经截止</span>
                  <span class="deadline-text" v-else>{{ toLocalTime(gt.deadline) }}</span>
                  <van-icon name="arrow" class="arrow-icon ml-12"
                            :style="{ transform: expandedTaskId === gt.id ? 'rotate(90deg)' : 'rotate(0deg)' }"/>
                </div>
              </div>
              <!-- 手风琴弹出面板 -->
              <div class="gai-task-detail-accordion" :class="{ 'is-expanded': expandedTaskId === gt.id }">
                <div class="gai-detail-inner">
                  <!-- 描述文本栏 -->
                  <div class="gai-desc-bar" v-html="renderMd(gt.description)"></div>
                  <!-- 底部操作按钮栏 -->
                  <div class="gai-submit-bar" v-if="!gt.isCompleted">
                    <!-- 状态1：有其他任务正在进行中，当前任务按钮禁用 -->
                    <button v-if="currentActiveTaskId && currentActiveTaskId !== gt.id" class="btn-submit" disabled>
                      开始探究任务
                    </button>
                    <!-- 状态2：当前任务未开始，可点击 -->
                    <button v-else-if="!gt.isCompleted && !gt.isExpired && currentActiveTaskId !== gt.id"
                            class="btn-submit start-btn" @click.stop="handleStartGaiTask(gt)"> 开始探究任务
                    </button>
                    <!-- 状态3：当前任务正在进行中，显示提交按钮 -->
                    <button v-else-if="currentActiveTaskId === gt.id" class="btn-submit submit-btn"
                            @click.stop="handleCallGaiSubmit"> 提交探究任务
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
    <!-- 全局 GAI 悬浮组件-->
    <GAI ref="globalGaiRef" roleSuffix="student" @submit-task="handleTaskSubmit"/>
  </div>
</template>

<script setup>
import {ref, reactive, nextTick, onMounted, onBeforeUnmount} from 'vue'
import {useRoute, useRouter} from 'vue-router'
import {showToast, showConfirmDialog} from 'vant'
import AppHeader from '@/components/AppHeader.vue'
import GAI from '@/components/GAI.vue'
import {get_course_detail, get_chapters, get_tasks, get_gai_tasks, submit_gai_task} from '@/api/course.js'
import MarkdownIt from 'markdown-it'
import texmath from 'markdown-it-texmath'
import katex from 'katex'
import DOMPurify from 'dompurify'

const md = new MarkdownIt({html: false, breaks: true}).use(texmath, {engine: katex, delimiters: 'dollars'})
const renderMd = (raw) => DOMPurify.sanitize(md.render(raw), {USE_PROFILES: {html: true, mathMl: true}})

const toLocalTime = (isoStr) => {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  return `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const route = useRoute()
const router = useRouter()
const courseId = route.params.courseId
const activeLeftTab = ref(route.query.tab || 'chapter')
const studentName = ref(localStorage.getItem('username') || '')
const courseInfo = ref({id: '', name: '', teacher: '', cover: ''})

// 记录当前展开面板的任务 ID
const expandedTaskId = ref('')
// 记录当前激活（正在进行）的任务 ID
const currentActiveTaskId = ref('')

const switchTab = (tab) => {
  activeLeftTab.value = tab
  router.replace({query: {...route.query, tab}})
}

const chapterList = ref([])
const taskList = ref([])
const gaiTaskList = ref([])

/** 获取课程所有基础数据 */
const fetchCourseData = async () => {
  const detailRes = await get_course_detail(courseId)
  const detail = detailRes.data
  const RESOURCE_BASE_URL = import.meta.env.VITE_RESOURCE_BASE_URL || ''
  courseInfo.value = {
    id: detail.course_id,
    name: detail.course_name,
    teacher: detail.teacher_name,
    cover: detail.course_cover.startsWith('http') ? detail.course_cover : `${RESOURCE_BASE_URL}${detail.course_cover}`
  }

  const chaptersRes = await get_chapters(courseId)
  chapterList.value = chaptersRes.data.chapters.map(ch => ({
    id: ch.chapter_id,
    title: ch.chapter_title,
    expanded: true,
    subTasks: ch.sub_tasks.map(st => ({
      id: st.section_id,
      title: st.section_title,
      type: st.section_type,
      isCompleted: st.is_completed
    }))
  }))

  const tasksRes = await get_tasks(courseId)
  const now = Date.now()
  taskList.value = tasksRes.data.tasks.map(t => ({
    id: t.task_id,
    title: t.task_title,
    deadline: t.deadline,
    isExpired: t.deadline !== '' && new Date(t.deadline).getTime() < now,
    isCompleted: t.is_completed
  }))

  const gaiTasksRes = await get_gai_tasks(courseId)
  gaiTaskList.value = gaiTasksRes.data.gai_tasks.map(gt => ({
    id: gt.analysis_task_id,
    title: gt.analysis_task_title,
    description: gt.task_description,
    deadline: gt.deadline,
    isExpired: gt.deadline !== '' && new Date(gt.deadline).getTime() < now,
    isCompleted: gt.is_completed,
    expanded: false,
    inputText: '',
    isWaitingAI: false,
    chatHistory: []
  }))

  const taskId = route.query.taskId
  if (taskId) {
    const targetTab = route.query.tab || 'task'
    switchTab(targetTab)
    nextTick(() => {
      if (targetTab === 'task') {
        const task = taskList.value.find(t => t.id === taskId)
        if (task) handleTaskClick(task)
      }
    })
  }
}

onMounted(() => fetchCourseData())

const toggleChapter = (idx) => chapterList.value[idx].expanded = !chapterList.value[idx].expanded

// === GAI 任务逻辑 ===
const globalGaiRef = ref(null)

/** 切换手风琴面板的展开/折叠 */
const handleToggleGaiPanel = (task) => {
  expandedTaskId.value = expandedTaskId.value === task.id ? '' : task.id
}

/** 点击开始任务：防并发校验与状态初始化 */
const handleStartGaiTask = (task) => {
  if (!globalGaiRef.value) return
  if (globalGaiRef.value.isInTaskMode) {
    showToast({message: '请先完成或提交当前正在进行的 GAI 探究任务', type: 'fail', position: 'bottom'})
    return
  }
  currentActiveTaskId.value = task.id
  expandedTaskId.value = task.id
  const promptText = `这是系统发送的信息：上下文：该同学正在进行《${courseInfo.value.name}》课程的任务。任务描述：${task.description}。引导学生围绕该任务描述进行思考、提问并完成探究。`
  globalGaiRef.value.startTaskMode({
    courseName: courseInfo.value.name,
    taskTitle: task.title,
    taskDesc: task.description,
    promptText: promptText,
    courseId: courseId,
    taskId: task.id,
    apiUrl: '/service/chat/stream/gai_chat'
  })
}

/** 触发 GAI 组件内部的提交校验与事件抛出 */
const handleCallGaiSubmit = async () => {
  if (!globalGaiRef.value) return

  try {
    // 弹出确认对话框
    await showConfirmDialog({
      title: '提交确认',
      message: '确认提交该探究任务吗？提交后将无法修改。'
    })
    // 用户点击确认后，执行提交
    globalGaiRef.value.handleSubmitTask()
  } catch (error) {
    // 用户点击取消，捕捉异常，不做任何处理
  }
}

/** 监听 GAI 组件抛出的提交事件 */
const handleTaskSubmit = async ({taskId, courseId: cId, messages}) => {
  try {
    await submit_gai_task(cId, taskId, messages)
    showToast({message: '提交成功', type: 'success'})
    const targetTask = gaiTaskList.value.find(t => t.id === taskId)
    if (targetTask) targetTask.isCompleted = true
    currentActiveTaskId.value = ''
    expandedTaskId.value = ''
    globalGaiRef.value.exitTaskMode()
  } catch (error) {
    console.error('提交任务失败:', error)
  }
}

const handleSubTaskClick = (section) => {
  router.push({path: '/course/study', query: {courseId: courseId, sectionId: section.id, type: section.type}})
}

const handleTaskClick = (task) => {
  router.push({path: '/course/task', query: {courseId: courseId, taskId: task.id}})
}

onBeforeUnmount(() => {
  if (globalGaiRef.value && globalGaiRef.value.isInTaskMode) {
    globalGaiRef.value.exitTaskMode()
  }
})
</script>

<style scoped src="../../styles/views/student/CourseStu.css"></style>
