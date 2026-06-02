<template>
  <div class="student-index-page page-fade-enter">
    <!-- 1. 顶部导航栏（强制复用 AppHeader，角色为学生） -->
    <AppHeader role="student" :userName="studentName || '学生'"/>

    <!-- 2. 页面主体（两栏布局） -->
    <div class="main-body">
      <!-- 左侧内容区域 (占用剩余宽度) -->
      <div class="left-content">
        <!-- ================= 板块一：学生个人信息卡片 (占高 30%) ================= -->
        <div class="section info-section">
          <!-- 头像区 -->
          <div class="avatar-area">
            <img :src="profile_img" alt="学生头像" class="student-avatar"/>
          </div>
          <!-- 信息区 -->
          <div class="info-area">
            <div class="student-name">{{ studentName }}</div>
            <div class="student-meta">学号：{{ studentId }}</div>
            <div class="student-meta">班级：{{ studentClass }}</div>
          </div>
          <!-- 数据区：本周每日学习时长折线图 -->
          <div class="data-area chart-area">
            <div class="today-study-badge">
              今日学习：<span class="highlight">{{ studyTime }}</span> 小时 / 24h
            </div>
            <div ref="chartRef" class="echarts-container"></div>
          </div>
        </div>

        <!-- ================= 板块二：待办学习任务列表 (占高 35%) ================= -->
        <div class="section todo-section">
          <div class="section-title">学习任务</div>
          <!-- 有数据时：垂直边缘发散模糊容器 -->
          <div class="vertical-scroll-container blur-vertical" v-if="todoList.length > 0">
            <div class="todo-item" v-for="task in todoList" :key="task.id" @click="goToTask(task)">
              <div class="task-left">
                <div class="status-dot" :class="{ 'is-done': task.completed }"></div>
                <span class="task-title" :class="{ 'text-done': task.completed }">{{ task.title }}</span>
              </div>
              <!-- 右侧：课程名 + 固定在最右侧的截止时间 -->
              <div class="task-right">
                <span class="task-course">{{ task.course }}</span>
                <span class="task-deadline">{{ task.deadlineText }}</span>
              </div>
            </div>
          </div>
          <!-- 无数据时：居中展示空状态 -->
          <div class="vertical-scroll-container" v-else style="display: flex; align-items: center; justify-content: center;">
            <van-empty description="任务列表空了" />
          </div>
        </div>

        <!-- ================= 板块三：已选课程横向滚动列表 (占高 35%) ================= -->
        <div class="section course-section">
          <div class="section-title">我的课程</div>
          <!-- 有数据时：水平边缘发散模糊容器 -->
          <div class="horizontal-scroll-container blur-horizontal" v-if="courseList.length > 0">
            <div class="course-card" v-for="course in courseList" :key="course.id" @click="goToCourse(course.id)">
              <img :src="course.cover" alt="课程封面" class="course-cover"/>
              <div class="course-info">
                <div class="course-name">{{ course.name }}</div>
                <div class="course-teacher">{{ course.teacher }}</div>
              </div>
            </div>
          </div>
          <!-- 无数据时：居中展示空状态 -->
          <div class="horizontal-scroll-container" v-else style="display: flex; align-items: center; justify-content: center;">
            <van-empty description="课程列表是空的" />
          </div>
        </div>
      </div>

      <!-- ================= 右侧 GAI 助手区域 (强制内嵌，高度 90%) ================= -->
      <div class="right-agi-wrapper">
        <!-- 新增传入 roleSuffix="student" -->
        <GAI ref="gaiRef" class="embedded-agi" roleSuffix="student" :overlay="false"/>
      </div>
    </div>
  </div>
</template>

<script setup>
import {ref, computed, onMounted, onBeforeUnmount, nextTick} from 'vue'
import {useRouter} from 'vue-router'
import * as echarts from 'echarts'
import AppHeader from '@/components/AppHeader.vue'
import GAI from '@/components/GAI.vue'
import {get_student_courses, get_student_tasks_todo} from '@/api/course.js'
import {get_student_weekly_study} from "@/api/student.js"

const router = useRouter()

// 获取 GAI 组件实例，用于挂载时强制打开
const gaiRef = ref(null)

// === 0. 全局资源前缀 ===
const RESOURCE_BASE_URL = import.meta.env.VITE_RESOURCE_BASE_URL

// === 1. 数据绑定与动态变量清单 ===
const profile_img = ref('https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg')
const studentName = ref('')
const studentId = ref('')
const studentClass = ref('')

// === 2. ECharts 折线图渲染逻辑 ===
const studyTimeList = ref([0, 0, 0, 0, 0, 0, 0])
const studyTime = computed(() => studyTimeList.value.length === 7 ? studyTimeList.value[6] : 0)
const chartRef = ref(null)
let myChart = ref(null)

const initChart = () => {
  if (!chartRef.value) return
  if (myChart.value) myChart.value.dispose()
  myChart.value = echarts.init(chartRef.value)
  const option = {
    grid: {top: 35, right: 10, bottom: 20, left: 30, containLabel: true},
    tooltip: {trigger: 'axis', formatter: '{b} : {c} 小时'},
    xAxis: {
      type: 'category',
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      axisLine: {lineStyle: {color: '#E0E0E0'}},
      axisLabel: {color: '#666666', fontSize: 12}
    },
    yAxis: {
      type: 'value',
      splitLine: {lineStyle: {color: '#F0F0F0', type: 'dashed'}},
      axisLabel: {color: '#666666', fontSize: 12}
    },
    series: [
      {
        data: studyTimeList.value,
        type: 'line',
        smooth: true,
        symbolSize: 6,
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
  myChart.value.setOption(option)
}

const handleResize = () => {
  if (myChart.value) myChart.value.resize()
}

// === 3. 生命周期与基础初始化 ===
onMounted(() => {
  studentName.value = localStorage.getItem("username")
  studentId.value = localStorage.getItem("id")
  studentClass.value = localStorage.getItem("user_class")
  fetchCourses()
  fetchWeeklyStudy()
  fetchTodoTasks()
  nextTick(() => {
    initChart()
    if (gaiRef.value) {
      gaiRef.value.isOpen = true
      if (gaiRef.value.togglePanel) {
        gaiRef.value.togglePanel(true)
      }
    }
  })
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (myChart.value) myChart.value.dispose()
})

// === 4. 数据请求与状态赋值 ===
const todoList = ref([])
const courseList = ref([])

const formatDeadline = (isoString) => {
  if (!isoString) return '无期限'
  const date = new Date(isoString)
  const M = String(date.getMonth() + 1).padStart(2, '0')
  const D = String(date.getDate()).padStart(2, '0')
  const h = String(date.getHours()).padStart(2, '0')
  const m = String(date.getMinutes()).padStart(2, '0')
  return `${M}-${D} ${h}:${m}`
}

const fetchCourses = async () => {
  const res = await get_student_courses(1)
  const {courses} = res.data
  courseList.value = courses.map(c => ({
    id: c.course_id,
    name: c.course_name,
    teacher: c.teacher_name,
    cover: c.course_cover.startsWith('http') ? c.course_cover : RESOURCE_BASE_URL + c.course_cover
  }))
}


/**
 * 获取学生本周每日学习时长
 */
const fetchWeeklyStudy = async () => {
  const res = await get_student_weekly_study()
  const rawSeconds = res.data.daily_seconds
  studyTimeList.value = rawSeconds.slice(0, 7).map(seconds => {
    return Number((seconds / 3600).toFixed(1)) // 3668秒 → 1.0小时
  })
  await nextTick()
  initChart()
}

/**
 * 检查是否为每日首次登录，并触发 GAI 主动问候与任务建议
 */
const checkAndSendFirstGreet = async () => {
  if (localStorage.getItem('is_first_show') === 'true' || gaiRef.value.allMessages.length === 0) {
    localStorage.setItem('is_first_show', false)
    await nextTick()
    if (gaiRef.value && gaiRef.value.sendSilentMessage) {
      const uncompletedTasks = todoList.value.filter(t => !t.completed)
      let taskContextStr = '当前没有待办任务'
      if (uncompletedTasks.length > 0) {
        taskContextStr = uncompletedTasks.map(t => `- 《${t.course}》: ${t.title} (截止时间: ${t.deadlineText})`).join('\n')
      }
      const currentTime = new Date().toLocaleString()
      const prompt = `这是系统发送的信息：上下文：该同学当前的未完成学习任务如下：\n${taskContextStr}\n，该用户刚刚登录上线，当前时间：${currentTime}，打个招呼，对方是${studentName.value}同学，根据以上任务清单，主动为该同学提供个性化的学习建议、时间规划或优先级排序指导。`
      await gaiRef.value.sendSilentMessage(prompt)
    }
  }
}

/**
 * 获取学生待办学习任务列表
 */
const fetchTodoTasks = async () => {
  const res = await get_student_tasks_todo()
  const {tasks, gai_tasks} = res.data
  const gaiTaskIds = new Set(gai_tasks.map(t => t.task_id))
  const allTasks = [...tasks, ...gai_tasks]
  todoList.value = allTasks.map(t => {
    // 强制校验：排查后端漏传 course_id 导致跳转 undefined 的问题
    if (!t.course_id) {
      console.error(`[数据异常] 任务 "${t.task_title}" (ID: ${t.task_id}) 缺失 course_id，请排查后端 /student/tasks-todo 接口！`)
    }
    return {
      id: t.task_id,
      courseId: t.course_id,
      title: t.task_title,
      course: t.course_name,
      completed: t.is_completed,
      isGai: gaiTaskIds.has(t.task_id),
      deadlineText: formatDeadline(t.deadline) // 提取并格式化截止时间
    }
  })
  // 数据赋值完成后，检查并发送每日首次问候
  checkAndSendFirstGreet()
}

// === 5. 路由跳转 ===
const goToCourse = (id) => {
  router.push(`/course/${id}`)
}

const goToTask = (task) => {
  if (task.isGai) {
    router.push({path: `/course/${task.courseId}`, query: {tab: 'gai-task', taskId: task.id}})
  } else {
    router.push({path: '/course/task', query: {courseId: task.courseId, taskId: task.id}})
  }
}
</script>

<!-- 严格的样式隔离，恢复外部引入 -->
<style scoped src="../../styles/views/student/Index.css"></style>
