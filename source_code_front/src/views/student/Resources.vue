<template>
  <div class="resources-page page-fade-enter">
    <AppHeader role="student" :userName="studentName || '学生'"/>

    <div class="main-body">
      <aside class="left-sidebar">
        <ul class="category-list">
          <li class="category-item active">
            <span>我的课程</span>
          </li>
        </ul>
      </aside>

      <main class="right-content">
        <div class="scroll-container" @scroll="handleScroll" ref="scrollContainerRef">
          <div v-if="loading" class="skeleton-grid">
            <div v-for="i in 8" :key="i" class="skeleton-card">
              <van-skeleton title :row="2"/>
            </div>
          </div>

          <div v-else class="course-grid">
            <!-- 加入班级卡片 -->
            <div class="course-card create-card" @click="showJoinModal = true">
              <div class="create-icon-wrapper">
                <van-icon name="plus" class="plus-icon"/>
              </div>
              <div class="create-text">加入班级</div>
            </div>

            <div
                class="course-card"
                v-for="course in courseList"
                :key="course.id"
                @click="goToCourse(course.id)"
            >
              <img :src="course.cover" alt="课程封面" class="course-cover" loading="lazy"/>
              <div class="course-info">
                <div class="course-title">{{ course.name }}</div>
                <div class="course-teacher">{{ course.teacher }}</div>
              </div>
            </div>
          </div>

          <div class="loading-more-area" v-if="loadingMore">
            <van-loading size="24px" vertical>加载更多课程...</van-loading>
          </div>

          <div
              class="no-more-area"
              v-if="!pagination.hasMore && !loading && courseList.length > 0"
          >
            <span>已经到底啦，没有更多课程了</span>
          </div>
        </div>
      </main>
    </div>

    <!-- 加入班级弹窗（推荐 Vant 4 的 v-model:show 双向绑定） -->
    <van-popup
        v-model:show="showJoinModal"
        class="join-modal-popup"
        position="center"
        :style="{ zIndex: 3000 }"
        teleport="body"
    >
      <div class="join-modal-content">
        <div class="join-modal-title">加入班级</div>
        <div class="join-input-wrapper">
          <input
              type="text"
              class="join-input"
              v-model="inviteCode"
              placeholder="请输入6位邀请码"
              maxlength="6"
              @input="handleInviteCodeInput"
          />
        </div>
        <div class="join-modal-buttons">
          <button class="join-btn btn-cancel" @click="showJoinModal = false">取消</button>
          <button
              class="join-btn btn-submit"
              :disabled="inviteCode.length !== 6"
              @click="handleJoinClass"
          >加入
          </button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import {ref, onMounted, onBeforeUnmount} from 'vue'
import {useRouter} from 'vue-router'
import {showToast} from 'vant'
import AppHeader from '@/components/AppHeader.vue'
import {get_student_courses, join_class} from '@/api/course.js'

const router = useRouter()

const courseList = ref([])
const pagination = ref({page: 1, hasMore: true})
const loading = ref(false)
const loadingMore = ref(false)
const scrollContainerRef = ref(null)
let abortController = null
const studentName = ref(localStorage.getItem('username') || '')
const RESOURCE_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
// 加入班级相关
const showJoinModal = ref(false)
const inviteCode = ref('')

const handleInviteCodeInput = () => {
  inviteCode.value = inviteCode.value.toUpperCase()
}

/**
 * 加入班级（无 try-catch，错误由全局拦截器处理）
 */
const handleJoinClass = async () => {
  if (inviteCode.value.length !== 6) return
  await join_class(inviteCode.value)
  showToast({message: '加入成功', type: 'success'})
  showJoinModal.value = false
  inviteCode.value = ''
  fetchCourses(false)
}

/**
 * 获取课程列表
 * - 无兼容层 firstDefined/unwrap
 * - 直接解构 res.data.courses
 * - 不写 || [] 等防御性兜底
 * - 请求取消使用 catch(() => void) 静默处理，不 console
 */
const fetchCourses = async (isAppend = false) => {
  if (!isAppend) {
    loading.value = true
    courseList.value = []
    pagination.value.page = 1
    pagination.value.hasMore = true
    if (scrollContainerRef.value) scrollContainerRef.value.scrollTop = 0
  } else {
    if (!pagination.value.hasMore) return
    loadingMore.value = true
  }

  if (abortController) abortController.abort()
  abortController = new AbortController()
  const signal = abortController.signal

  const res = await get_student_courses(pagination.value.page, signal).catch(() => void 0)
  if (!res) {
    loading.value = false
    loadingMore.value = false
    return
  }

  // 严格按信封解构，禁止兼容写法
  const {courses} = res.data

  const mapped = courses.map(c => ({
    id: c.course_id,
    name: c.course_name,
    teacher: c.teacher_name,
    cover: c.course_cover.startsWith('http') ? c.course_cover : RESOURCE_BASE_URL  + c.course_cover
  }))

  const newItems = mapped.filter(item => !courseList.value.some(existing => existing.id === item.id))
  if (isAppend) {
    courseList.value.push(...newItems)
  } else {
    courseList.value = newItems
  }

  // 分页结束判断：本次追加为空视为无更多
  if (isAppend && newItems.length === 0) {
    pagination.value.hasMore = false
  }

  loading.value = false
  loadingMore.value = false
}

const handleScroll = (e) => {
  const {scrollTop, clientHeight, scrollHeight} = e.target
  if (scrollHeight - scrollTop - clientHeight < 100) {
    if (!loadingMore.value && !loading.value && pagination.value.hasMore) {
      pagination.value.page += 1
      fetchCourses(true)
    }
  }
}

const goToCourse = (courseId) => {
  router.push(`/course/${courseId}`)
}

onMounted(() => {
  fetchCourses(false)
})

onBeforeUnmount(() => {
  if (abortController) abortController.abort()
})
</script>

<style scoped src="../../styles/views/student/Resources.css"></style>
