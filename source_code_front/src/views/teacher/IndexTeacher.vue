<template>
  <div class="teacher-index-page page-fade-enter">
    <!-- 1. 顶部导航栏（强制复用 AppHeader，身份标识 teacher） -->
    <AppHeader role="teacher" :userName="teacherName"/>
    <!-- 2. 页面主体：两栏布局 -->
    <div class="main-body">
      <!-- 左侧内容区域 -->
      <div class="left-content">
        <!-- 板块一：教师个人信息卡片 (占高 30%) -->
        <div class="section profile-section">
          <!-- 头像区 -->
          <div class="avatar-area">
            <img :src="profile_img" alt="教师头像" class="teacher-avatar"/>
          </div>
          <!-- 信息区 -->
          <div class="info-area">
            <div class="teacher-name">{{ teacherName }} 老师</div>
            <div class="teacher-meta">工号：{{ teacherId }}</div>
          </div>
        </div>
        <!-- 板块二：课程与学生学习详情看板 (占高 70%) -->
        <div class="section dashboard-section">
          <!-- 子板块一：课程列表 (宽度 25%) -->
          <div class="dash-col course-col">
            <div class="col-title">我的课程</div>
            <div class="scroll-list-container blur-vertical" ref="courseScrollRef" @scroll.passive="handleCourseScroll" v-if="displayedCourses.length > 0 && !loading.classLoading">
              <div
                v-for="cls in displayedCourses"
                :key="cls.id"
                class="course-card-mini"
                :class="{ 'is-active': selectedClassId === cls.id }"
                @click="handleClassSelect(cls.id)"
              >
                <img :src="cls.cover" alt="课程封面" loading="lazy" />
                <div class="card-name">{{ cls.name }}</div>
              </div>
            </div>
            <div class="empty-state-container" v-else-if="!loading.classLoading">
              <van-empty description="暂无课程" image="search" />
            </div>
            <van-skeleton v-else title :row="5" class="skeleton-padding"/>
          </div>
          <!-- 子板块二：学生列表 (宽度 15%) -->
          <div class="dash-col student-col">
            <div class="col-title">学生名单</div>
            <div class="scroll-list-container blur-vertical" v-if="studentList.length > 0 && !loading.studentLoading">
              <div v-for="stu in studentList" :key="stu.id" class="list-item" :class="{ 'is-active': selectedStudentId === stu.id }" @click="handleStudentSelect(stu.id)" >
                {{ stu.name }}
              </div>
            </div>
            <div class="empty-state-container" v-else-if="!loading.studentLoading && selectedClassId">
              <van-empty description="暂无学生" image="search" />
            </div>
            <van-skeleton v-else-if="loading.studentLoading" title :row="5" class="skeleton-padding"/>
          </div>
          <!-- 子板块三：学生详情展示区 (宽度 60%) -->
          <div class="dash-col detail-col">
            <!-- 未选择课程时的占位 -->
            <div class="detail-empty-tip" v-if="!selectedClassId && !loading.classLoading">
              <van-empty description="请先选择课程" image-size="80" />
            </div>
            <!-- 已选课程但无学生或未选学生时的占位 -->
            <div class="detail-empty-tip" v-else-if="selectedClassId && !selectedStudentId && !loading.studentLoading">
              <van-empty description="请选择学生查看详情" image-size="80" />
            </div>
            <!-- 详情加载骨架屏 -->
            <div v-else-if="loading.detailLoading" class="detail-skeleton">
              <van-skeleton title :row="3"/>
              <van-skeleton title :row="4" style="margin-top: 24px;"/>
            </div>
            <!-- 具体详情数据展示 -->
            <template v-else>
              <!-- 上部：本周每日学习时长折线图 (高度 40%) -->
              <div class="chart-area">
                <template v-if="studyTimeList.length > 0">
                  <!-- ECharts 容器 -->
                  <div ref="chartRef" class="echarts-container"></div>
                  <!-- 悬浮的今日累计时长提示 -->
                  <div class="today-study-badge">
                    今日学习：<span class="highlight">{{ todayStudyTime }}</span> 小时 / 24h
                  </div>
                </template>
                <div class="chart-empty" v-else>
                  <van-empty description="暂无学习记录" image-size="80" />
                </div>
              </div>
              <!-- 下部：学习情况分析文本块 (高度 60%) -->
              <div class="analysis-area">
                <div class="analysis-title">{{ currentStudentName }} - 综合学情分析</div>
                <div class="analysis-content-scroll blur-vertical">
                  <template v-if="renderedAnalysisText">
                    <!-- 流式输出的 Markdown 内容 -->
                    <div class="analysis-text markdown-body" v-html="renderedAnalysisText"></div>
                  </template>
                  <div class="text-empty" v-else>
                    <van-empty description="暂无学情分析数据" image-size="80" />
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
      <!-- 右侧 GAI 助手区域 -->
      <div class="right-agi-wrapper">
        <!-- 新增传入 roleSuffix="teacher" -->
        <AGI ref="gaiRef" class="embedded-agi" roleSuffix="teacher" :overlay="false"/>
      </div>
    </div>
  </div>
</template>

<script setup>
import {ref, reactive, computed, onMounted, watch, nextTick, onBeforeUnmount} from 'vue'
import * as echarts from 'echarts'
import AppHeader from '@/components/AppHeader.vue'
import AGI from '@/components/GAI.vue'
import MarkdownIt from 'markdown-it'
import texmath from 'markdown-it-texmath'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import DOMPurify from 'dompurify'
import {get_teacher_courses, get_course_students, get_analysis_ai_text_for_student_study} from '@/api/course.js'
import {get_student_weekly_study_in_course} from "@/api/student.js";

const gaiRef = ref(null)

// === 常量定义 ===
const BATCH_SIZE = 5

// === 数据绑定与状态变量清单 ===
const profile_img = ref('https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg')
const teacherName = ref('')
const teacherId = ref('')

// 课程列表状态改造：全量数据与分页渲染数据分离
const allCourses = ref([])
const displayedCourses = ref([])
const courseScrollRef = ref(null)

const selectedClassId = ref('')
const studentList = ref([])
const selectedStudentId = ref('')
const studyTimeList = ref([])
const loading = reactive({
  classLoading: true,
  studentLoading: false,
  detailLoading: false
})

// === 计算属性 ===
const currentClassName = computed(() => {
  const cls = allCourses.value.find(c => c.id === selectedClassId.value)
  return cls ? cls.name : '课程'
})

const currentStudentName = computed(() => {
  const stu = studentList.value.find(s => s.id === selectedStudentId.value)
  return stu ? stu.name : '学生'
})

const todayStudyTime = computed(() => {
  if (studyTimeList.value.length === 7) {
    return studyTimeList.value[6]
  }
  return 0
})

// === 图表逻辑 ===
const chartRef = ref(null)
let myChart = null
const initChart = () => {
  if (!chartRef.value) return
  if (myChart) myChart.dispose()
  myChart = echarts.init(chartRef.value)
  const option = {
    grid: {top: 30, right: 20, bottom: 20, left: 30, containLabel: true},
    tooltip: {trigger: 'axis', formatter: '{b} : {c} 小时'},
    xAxis: {
      type: 'category',
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      axisLine: {lineStyle: {color: '#E0E0E0'}},
      axisLabel: {color: '#666666'}
    },
    yAxis: {
      type: 'value',
      splitLine: {lineStyle: {color: '#F0F0F0', type: 'dashed'}},
      axisLabel: {color: '#666666'}
    },
    series: [
      {
        data: studyTimeList.value,
        type: 'line',
        smooth: true,
        symbolSize: 8,
        itemStyle: {color: '#4A90E2'},
        lineStyle: {width: 3, color: '#4A90E2'},
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            {offset: 0, color: 'rgba(74, 144, 226, 0.3)'},
            {offset: 1, color: 'rgba(74, 144, 226, 0)'}
          ])
        }
      }
    ]
  }
  myChart.setOption(option)
}
watch(() => studyTimeList.value, () => {
  nextTick(() => {
    initChart()
  })
}, {deep: true})
const handleResize = () => {
  if (myChart) myChart.resize()
}

// ==== Markdown 渲染器函数 ====
const md = new MarkdownIt({html: false, breaks: true}).use(texmath, {engine: katex, delimiters: 'dollars'})
const renderMarkdown = (raw) => {
  return DOMPurify.sanitize(md.render(raw), {USE_PROFILES: {html: true, mathMl: true}})
}
const renderedAnalysisText = ref('')
let streamTimer = null
const startAnalysisStream = (fullText) => {
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

// === 本地无感分页逻辑 ===
const loadNextCourses = () => {
  const currentLen = displayedCourses.value.length
  if (currentLen >= allCourses.value.length) return
  const nextBatch = allCourses.value.slice(currentLen, currentLen + BATCH_SIZE)
  displayedCourses.value.push(...nextBatch)
}

const handleCourseScroll = () => {
  if (!courseScrollRef.value) return
  const container = courseScrollRef.value
  const currentLen = displayedCourses.value.length

  // 边界拦截：数据已全部加载完，或当前批次不是满的（说明是最后一批不足5张的残余）
  if (currentLen >= allCourses.value.length || currentLen % BATCH_SIZE !== 0) return

  // 获取当前已渲染的所有卡片 DOM
  const cards = container.querySelectorAll('.course-card-mini')
  // 目标是当前批次倒数第二张卡片（即 N*5 - 2 的索引）
  const targetCardIndex = currentLen - 2
  // 容错降级：如果找倒数第二张失败（理论上不会），降级找最后一张
  const targetCard = cards[targetCardIndex] || cards[currentLen - 1]

  if (targetCard) {
    const { scrollTop, clientHeight } = container
    // 当可视区域底部触达目标卡片顶部时，触发下一批加载
    if (scrollTop + clientHeight >= targetCard.offsetTop) {
      loadNextCourses()
    }
  }
}

// === 数据联动逻辑 ===
const fetchClasses = async () => {
  loading.classLoading = true
  const res = await get_teacher_courses(1)
  const {courses} = res.data

  // 严格信任后端结构，直接映射并拼接资源根路径
  allCourses.value = courses.map(item => ({
    id: item.course_id,
    name: item.course_name,
    cover: `${import.meta.env.VITE_RESOURCE_BASE_URL}${item.course_cover}`
  }))

  loading.classLoading = false

  // 初始化加载第一批（5张）
  loadNextCourses()

  // 自动选中第一门课程
  if (allCourses.value.length > 0) {
    handleClassSelect(allCourses.value[0].id)
  }
}

const handleClassSelect = async (classId) => {
  if (selectedClassId.value === classId && studentList.value.length > 0) return
  selectedClassId.value = classId
  selectedStudentId.value = ''
  loading.studentLoading = true
  studyTimeList.value = []
  renderedAnalysisText.value = ''
  if (myChart) {
    myChart.dispose()
    myChart = null
  }
  const res = await get_course_students(classId)
  const {students} = res.data
  studentList.value = students.map(item => ({id: item.id, name: item.name}))
  loading.studentLoading = false
  if (studentList.value.length > 0) {
    handleStudentSelect(studentList.value[0].id)
  }
}

const handleStudentSelect = async (studentId) => {
  if (selectedStudentId.value === studentId && studyTimeList.value.length === 7) return
  selectedStudentId.value = studentId
  loading.detailLoading = true
  if (myChart) {
    myChart.dispose()
    myChart = null
  }
  const [weeklyRes, aiRes] = await Promise.all([
    get_student_weekly_study_in_course(selectedClassId.value, studentId),
    get_analysis_ai_text_for_student_study(selectedClassId.value, studentId)
  ])
  studyTimeList.value = weeklyRes.data.daily_seconds.map(n => (Number(n) / 3600).toFixed(1))
  const aiText = aiRes.data.description
  startAnalysisStream(aiText)
  loading.detailLoading = false
}

// === 生命周期 ===
onMounted(() => {
  teacherId.value = localStorage.getItem('id')
  teacherName.value = localStorage.getItem('username')
  fetchClasses()
  window.addEventListener('resize', handleResize)
  nextTick(() => {
    if (gaiRef.value) {
      gaiRef.value.isOpen = true
      if (localStorage.getItem('is_first_show') === 'true' || gaiRef.value.allMessages.length === 0) {
        const currentTime = new Date().toLocaleString()
        gaiRef.value.sendSilentMessage(`这是系统发送的信息：该用户刚刚登录上线，当前时间：${currentTime}，打个招呼，对方是${teacherName.value}老师，简要的介绍一下自己吧！`)
        localStorage.setItem('is_first_show', false)
      }
    }
  })
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (myChart) myChart.dispose()
  if (streamTimer) clearInterval(streamTimer)
})
</script>
<!-- 严格遵守样式隔离规则，仅通过 src 引入 -->
<style scoped src="../../styles/views/teacher/IndexTeacher.css"></style>
