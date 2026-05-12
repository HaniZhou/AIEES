<template>
  <div class="task-detail-page page-fade-enter">
    <!-- 页面主体：垂直三段式布局 -->
    <div class="main-body">
      <!-- 顶部固定信息栏 -->
      <div class="top-info-bar">
        <div class="info-left">
          <div class="back-btn" @click="goBack">
            <van-icon name="arrow-left" size="20" color="#333333" />
          </div>
          <div class="test-name">{{ testInfo.title }}</div>
          <div class="test-count">（共 {{ testInfo.total }} 题）</div>
        </div>
        <div class="info-right">
          <div class="test-deadline" :class="{ 'is-urgent': testInfo.isUrgent }" >
            截止：{{ testInfo.deadline }}
          </div>
        </div>
      </div>

      <!-- 中间题目区 (根据状态增加禁用态 class) -->
      <div class="middle-scroll-area blur-vertical">
        <div class="question-list" :class="{ 'is-disabled-view': pageState !== 'answering' }" >
          <!-- 作答总结卡片 (仅已提交状态且AI非批改中显示) -->
          <div class="review-summary-card" v-if="pageState === 'submitted' && reviewInfo.ai_analysis !== 'grading'" >
            <div class="summary-header">作答总结</div>
            <div class="summary-score">最终得分：{{ reviewInfo.task_score }}</div>
            <div class="summary-analysis">
              <div class="analysis-title">AI 分析：</div>
              <div class="analysis-text markdown-body" v-html="renderedAnalysisText" ></div>
            </div>
          </div>

          <!-- 题目卡片循环渲染 -->
          <div class="question-card" v-for="(q, index) in questionList" :key="q.id" >
            <div class="card-header">
              <div class="q-num">第 {{ index + 1 }} 题</div>
              <div class="q-type-tag">{{ getTypeName(q.type) }}</div>
            </div>
            <div class="q-title">{{ q.title }}</div>

            <!-- (一) 单选题 -->
            <div v-if="q.type === 'single'" class="options-container">
              <div class="option-row" v-for="opt in q.options" :key="opt.id" @click="q.answer = opt.id" :class="{
                  'is-correct': pageState === 'submitted' && q.student_answer == opt.id && q.student_answer == q.correct_answer,
                  'is-wrong': pageState === 'submitted' && q.student_answer == opt.id && q.student_answer != q.correct_answer,
                  'is-missed': pageState === 'submitted' && q.student_answer != q.correct_answer && q.correct_answer == opt.id,
                }" >
                <div class="radio-circle" :class="{ 'is-active': q.answer == opt.id }" >
                  <div class="radio-dot" v-if="q.answer == opt.id"></div>
                </div>
                <div class="option-text">{{ opt.content }}</div>
              </div>
            </div>

            <!-- (二) 多选题 -->
            <div v-else-if="q.type === 'multiple'" class="options-container">
              <div class="option-row" v-for="opt in q.options" :key="opt.id" @click="toggleMultiple(q, opt.id)" :class="{
                  'is-correct': pageState === 'submitted' && q.student_answer.includes(opt.id) && q.correct_answer.includes(opt.id),
                  'is-wrong': pageState === 'submitted' && q.student_answer.includes(opt.id) && !q.correct_answer.includes(opt.id),
                  'is-missed': pageState === 'submitted' && !q.student_answer.includes(opt.id) && q.correct_answer.includes(opt.id),
                }" >
                <div class="checkbox-square" :class="{ 'is-active': q.answer.includes(opt.id) }" >
                  <van-icon v-if="q.answer.includes(opt.id)" name="success" size="14" color="#FFFFFF" />
                </div>
                <div class="option-text">{{ opt.content }}</div>
              </div>
            </div>

            <!-- (三) 判断题 -->
            <div v-else-if="q.type === 'judge'" class="judge-container">
              <div class="judge-btn" :class="{
                  'is-active': q.answer == 'true',
                  'is-correct': pageState === 'submitted' && q.student_answer == 'true' && q.student_answer == q.correct_answer,
                  'is-wrong': pageState === 'submitted' && q.student_answer == 'true' && q.student_answer != q.correct_answer,
                  'is-missed': pageState === 'submitted' && q.student_answer != q.correct_answer && q.correct_answer == 'true',
                }" @click="q.answer = 'true'" >
                正确
              </div>
              <div class="judge-btn" :class="{
                  'is-active': q.answer == 'false',
                  'is-correct': pageState === 'submitted' && q.student_answer == 'false' && q.student_answer == q.correct_answer,
                  'is-wrong': pageState === 'submitted' && q.student_answer == 'false' && q.student_answer != q.correct_answer,
                  'is-missed': pageState === 'submitted' && q.student_answer != q.correct_answer && q.correct_answer == 'false',
                }" @click="q.answer = 'false'" >
                错误
              </div>
            </div>

            <!-- (四) 主观题 -->
            <div v-else-if="q.type === 'subjective'" class="subjective-container">
              <textarea class="subjective-input" v-model="q.answer" placeholder="请输入你的答案…" :readonly="pageState !== 'answering'" ></textarea>
              <div v-if="pageState === 'submitted' && q.refer_answer" class="refer-answer-box" >
                <div class="refer-answer-title">参考答案：</div>
                <div class="refer-answer-text">{{ q.refer_answer }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部固定操作栏 (三态切换) -->
      <div class="bottom-action-bar">
        <template v-if="pageState === 'answering'">
          <div class="warning-text" v-if="!allAnswered">请完成作答</div>
          <button class="submit-btn" :class="{ 'is-disabled': !allAnswered, 'is-active': allAnswered }" :disabled="!allAnswered" @click="submitTask" >
            提交作答
          </button>
        </template>
        <template v-else-if="pageState === 'submitted'">
          <div class="status-text is-submitted">已提交</div>
        </template>
        <template v-else-if="pageState === 'expired'">
          <div class="status-text is-expired">已截止</div>
        </template>
      </div>
    </div>
    <GAI role-suffix="student" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showDialog } from 'vant'
import GAI from '@/components/GAI.vue'
import { get_task_detail, submit_task_answers, get_task_review } from '@/api/course.js'
import MarkdownIt from 'markdown-it'
import texmath from 'markdown-it-texmath'
import katex from 'katex'
import DOMPurify from 'dompurify'
import 'katex/dist/katex.min.css'
import 'markdown-it-texmath/css/texmath.css'

const md = new MarkdownIt({ html: false, breaks: true }).use(texmath, { engine: katex, delimiters: 'dollars', })

const renderMarkdown = (raw) => DOMPurify.sanitize(md.render(raw), { USE_PROFILES: { html: true, mathMl: true }, })

const router = useRouter()
const route = useRoute()

const courseId = route.query.courseId
const taskId = route.query.taskId

const testInfo = ref({
  title: '',
  total: 0,
  deadline: '',
  isUrgent: false,
  rawDeadlineTime: 0,
})

const isCompleted = ref(false)
const questionList = ref([])
const reviewInfo = ref({
  task_score: 0,
  ai_analysis: ''
})

const renderedAnalysisText = ref('')
let streamTimer = null

const pageState = computed(() => {
  if (isCompleted.value) return 'submitted'
  const now = Date.now()
  if (testInfo.value.rawDeadlineTime > 0 && now > testInfo.value.rawDeadlineTime) return 'expired'
  return 'answering'
})

const fetchTaskDetail = async () => {
  const res = await get_task_detail(courseId, taskId)
  const { task_title, deadline, quiz, is_completed } = res.data

  isCompleted.value = is_completed
  const deadlineTime = deadline ? new Date(deadline).getTime() : 0
  testInfo.value.rawDeadlineTime = deadlineTime
  const isUrgent = deadlineTime > 0 && deadlineTime - Date.now() < 24 * 60 * 60 * 1000

  const formatLocal = (isoStr) => {
    if (!isoStr) return ''
    const d = new Date(isoStr)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }

  testInfo.value = {
    title: task_title,
    total: quiz.length,
    deadline: formatLocal(deadline),
    isUrgent,
    rawDeadlineTime: deadlineTime,
  }

  questionList.value = quiz.map((q) => ({
    id: q.question_id,
    type: q.type,
    title: q.title,
    options: q.options.map((opt) => ({
      id: String(opt.id),
      content: opt.content
    })),
    answer: q.type === 'multiple' ? [] : '',
    student_answer: q.type === 'multiple' ? [] : '',
    correct_answer: q.type === 'multiple' ? [] : '',
    refer_answer: '',
  }))

  if (is_completed) {
    fetchTaskReview()
  }
}

const fetchTaskReview = async () => {
  const res = await get_task_review(courseId, taskId)
  const { task_score, ai_analysis, questions: reviewQuestions } = res.data

  reviewInfo.value = {
    task_score,
    ai_analysis
  }

  reviewQuestions.forEach((rq) => {
    const target = questionList.value.find((q) => q.id === rq.question_id)
    if (!target) return

    if (target.type === 'single' || target.type === 'judge') {
      const cAns = Array.isArray(rq.correct_answer) ? rq.correct_answer[0] : rq.correct_answer
      target.correct_answer = String(cAns)
      const sAns = Array.isArray(rq.student_answer) ? rq.student_answer[0] : rq.student_answer
      target.student_answer = String(sAns || '')
      target.answer = String(sAns || '')
    } else if (target.type === 'multiple') {
      const cAnsList = Array.isArray(rq.correct_answer) ? rq.correct_answer : []
      target.correct_answer = cAnsList.map(String)
      const sAnsList = Array.isArray(rq.student_answer) ? rq.student_answer : []
      target.student_answer = sAnsList.map(String)
      target.answer = sAnsList.map(String)
    } else if (target.type === 'subjective') {
      target.refer_answer = rq.correct_answer || ''
      target.correct_answer = ''
      target.student_answer = rq.student_answer || ''
      target.answer = rq.student_answer || ''
    }
  })

  if (ai_analysis && ai_analysis !== 'grading') {
    startStream(ai_analysis)
  }
}

const startStream = (fullText) => {
  if (streamTimer) clearInterval(streamTimer)
  renderedAnalysisText.value = ''
  const targetDuration = 7500
  const interval = 30
  const totalSteps = targetDuration / interval
  const chunkSize = Math.max(1, Math.ceil(fullText.length / totalSteps))
  let index = 0

  streamTimer = setInterval(() => {
    const partial = fullText.slice(0, index)
    renderedAnalysisText.value = renderMarkdown(partial)
    index += chunkSize
    if (index >= fullText.length) {
      renderedAnalysisText.value = renderMarkdown(fullText)
      clearInterval(streamTimer)
      streamTimer = null
    }
  }, interval)
}

onMounted(() => {
  fetchTaskDetail()
})

onBeforeUnmount(() => {
  if (streamTimer) clearInterval(streamTimer)
})

const getTypeName = (type) => {
  const map = {
    single: '单选题',
    multiple: '多选题',
    judge: '判断题',
    subjective: '主观题',
  }
  return map[type] || '未知题型'
}

const goBack = () => {
  router.back()
}

const toggleMultiple = (question, optionId) => {
  const index = question.answer.indexOf(optionId)
  if (index > -1) {
    question.answer.splice(index, 1)
  } else {
    question.answer.push(optionId)
  }
}

const allAnswered = computed(() => {
  return questionList.value.every((q) => {
    if (q.type === 'single' || q.type === 'judge') return q.answer !== ''
    if (q.type === 'multiple') return q.answer.length > 0
    if (q.type === 'subjective') return q.answer.trim().length > 0
    return false
  })
})

const submitTask = () => {
  if (!allAnswered.value) return

  showDialog({
    title: '确认提交',
    message: '提交后将无法修改答案，确认要交卷吗？',
    showCancelButton: true,
  })
    .then(async () => {
      const answers = questionList.value.map((q) => ({
        question_id: q.id,
        answer: q.answer,
      }))
      await submit_task_answers(courseId, taskId, answers)
      showToast({ message: '提交成功！', type: 'success' })
      setTimeout(() => {
        location.reload()
      }, 1500)
    })
    .catch(() => {})
}
</script>

<style scoped src="../../styles/views/student/TaskDetail.css"></style>
