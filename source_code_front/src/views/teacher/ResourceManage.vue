<template>
  <div class="course-management-page page-fade-enter">
    <!-- 1. 全局顶部导航栏（复用 AppHeader，身份标识 teacher） -->
    <AppHeader role="teacher" :userName="teacherName"/>

    <!-- 2. 页面主体：左侧"我的课程" + 右侧课程内容区 -->
    <div class="main-body">
      <!-- 左侧：仅保留"我的课程"入口 -->
      <aside class="left-sidebar">
        <ul class="category-list">
          <li class="category-item special-item active">
            <span>我的课程</span>
          </li>
        </ul>
      </aside>

      <!-- 右侧：课程内容区 -->
      <main class="right-content">
        <div class="scroll-container blur-vertical" @scroll="handleScroll" ref="scrollContainerRef">
          <!-- 首次加载骨架屏 -->
          <div v-if="loading" class="skeleton-grid">
            <div v-for="i in 8" :key="i" class="skeleton-card">
              <van-skeleton title :row="2"/>
            </div>
          </div>

          <!-- 课程数据网格布局 (每行 4 个) -->
          <div v-else class="course-grid">
            <!-- 创建新课程卡片（始终作为第一个） -->
            <div class="course-card create-card" @click="openCreateModal">
              <div class="create-icon-wrapper">
                <van-icon name="plus" class="plus-icon"/>
              </div>
              <div class="create-text">创建新课程</div>
            </div>

            <!-- 标准课程卡片 -->
            <div
              class="course-card standard-card"
              v-for="course in courseList"
              :key="course.id"
              @click="goToCourseEdit(course.id)"
            >
              <img :src="course.cover" alt="课程封面" class="course-cover" loading="lazy" />
              <div class="course-info">
                <div class="course-title">{{ course.name }}</div>
                <div class="course-teacher">{{ course.teacher }}</div>
              </div>
            </div>
          </div>

          <!-- 底部加载提示 -->
          <div class="loading-more-area" v-if="loadingMore">
            <van-loading size="24px" vertical>加载更多课程...</van-loading>
          </div>
          <div class="no-more-area" v-if="!pagination.hasMore && !loading && courseList.length > 0">
            <span>已经到底啦</span>
          </div>
        </div>
      </main>
    </div>

    <!-- ================= 全局模态浮层（Teleport 到 body） ================= -->
    <Teleport to="body">
      <transition name="fade-scale">
        <div v-if="showCreateModal" class="global-modal-overlay">
          <div class="global-modal-content">
            <!-- 一（10%）：标题区 -->
            <div class="modal-section section-title">
              <h2 class="modal-title">创建新课程</h2>
            </div>

            <!-- 二（55%）：左右两栏 —— 左侧封面上传 + 右侧输入框 -->
            <div class="modal-section section-form">
              <div class="form-left" :class="{ 'has-error': coverError, 'shake': coverShaking }">
                <van-uploader v-model="newCourseForm.cover" max-count="1" :after-read="onCoverRead">
                  <div class="upload-placeholder cover-upload">
                    <van-icon name="plus" size="28" color="#4A90E2"/>
                    <span>上传封面</span>
                  </div>
                </van-uploader>
                <div v-if="coverError" class="error-msg">请上传课程封面</div>
              </div>

              <div class="form-right">
                <!-- 课程名称 -->
                <div class="form-group" :class="{ 'has-error': courseNameError, 'shake': courseNameShaking }">
                  <input
                    type="text"
                    class="form-input"
                    v-model="newCourseForm.course_name"
                    placeholder="请输入课程名称"
                    @focus="clearCourseNameError"
                  />
                  <div class="error-msg" v-if="courseNameError">请输入课程名称</div>
                </div>

                <!-- 添加学习班级（点击弹出复选框） -->
                <div class="form-group class-select-wrapper" ref="classSelectRef">
                  <div class="class-select-trigger">
                    <input
                      type="text"
                      class="class-search-input"
                      v-model="classDisplayText"
                      @input="classSearchKeyword = classDisplayText"
                      @focus="openClassPopup"
                      placeholder="搜索并添加学习班级"
                      @click.stop
                    />
                    <van-icon
                      name="arrow-down"
                      class="trigger-arrow"
                      :class="{ 'trigger-arrow-open': showClassPopup }"
                      @click.stop="toggleClassPopup"
                    />
                  </div>
                  <transition name="popup-fade">
                    <div v-if="showClassPopup" class="class-popup" @click.stop>
                      <div v-if="classListLoading" class="class-popup-status">
                        <van-loading size="20" color="#4A90E2"/>
                      </div>
                      <div v-else-if="filteredClassList.length === 0" class="class-popup-status">
                        未找到匹配的班级
                      </div>
                      <div v-else class="class-popup-list">
                        <van-checkbox-group v-model="selectedClasses">
                          <div v-for="cls in filteredClassList" :key="cls.id" class="class-popup-item">
                            <van-checkbox :name="cls.class_name" shape="square">
                              {{ cls.class_name }}
                            </van-checkbox>
                          </div>
                        </van-checkbox-group>
                      </div>
                    </div>
                  </transition>
                </div>

                <!-- 教师姓名（只读） -->
                <div class="form-group">
                  <input type="text" class="form-input input-disabled" v-model="teacherName" disabled />
                </div>
              </div>
            </div>

            <!-- 三（25%）：教案 Word 上传区 -->
            <div class="modal-section section-word">
              <div class="word-upload-wrapper" :class="{ 'has-error': wordError, 'shake': wordShaking }" @click="triggerWordUpload">
                <input ref="wordInputRef" type="file" accept=".docx" style="display: none" @change="onWordFileChange" />
                <div class="word-upload-placeholder">
                  <van-icon name="description" size="24" color="#4A90E2"/>
                  <span v-if="!wordFileName" class="word-upload-text">上传教案 Word 文档</span>
                  <span v-else class="word-file-name">{{ wordFileName }}</span>
                </div>
                <div v-if="parsingWord" class="parsing-overlay">
                  <van-loading type="spinner" size="22" color="#4A90E2"/>
                  <span class="parsing-text">正在解析word文档</span>
                </div>
              </div>
              <div class="word-hint" v-if="!wordError">GAI系统将会分析您的课程教案资料，用于辅助您进行课堂教学。</div>
              <div class="error-msg" v-else>请上传并解析教案文档</div>
            </div>

            <!-- 四（10%）：底部按钮区 -->
            <div class="modal-section section-buttons">
              <button class="modal-btn btn-cancel" @click="closeCreateModal">取消</button>
              <button class="modal-btn btn-submit" :disabled="parsingWord" @click="submitCreateCourse">
                提交
              </button>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import AppHeader from '@/components/AppHeader.vue'
import { get_all_classes } from '@/api/classes.js'

/**
 * Word 文档解析依赖（需提前安装）：
 * npm install mammoth turndown
 */
import mammoth from 'mammoth'
import TurndownService from 'turndown'
import { create_new_course, get_teacher_courses } from "@/api/course.js"

const teacherName = ref(localStorage.getItem('username'))
const router = useRouter()

// ==================== 页面级状态 ====================
const courseList = ref([])
const pagination = reactive({ page: 1, hasMore: true })
const loading = ref(false)
const loadingMore = ref(false)
const scrollContainerRef = ref(null)

// ==================== 创建课程模态框状态 ====================
const showCreateModal = ref(false)
const parsingWord = ref(false)
const wordFileName = ref('')
const wordInputRef = ref(null)
let parseAborted = false

// --- 学习班级相关状态 ---
const showClassPopup = ref(false)
const classList = ref([])
const classListLoading = ref(false)
const selectedClasses = ref([])
const classSelectRef = ref(null)
const classDisplayText = ref('')
const classSearchKeyword = ref('')

const filteredClassList = computed(() => {
  let list = classList.value
  if (classSearchKeyword.value.trim()) {
    const query = classSearchKeyword.value.trim().toLowerCase()
    list = list.filter(cls => cls.class_name.toLowerCase().includes(query))
  }
  return [...list].sort((a, b) => {
    const aSelected = selectedClasses.value.includes(a.class_name) ? 0 : 1
    const bSelected = selectedClasses.value.includes(b.class_name) ? 0 : 1
    return aSelected - bSelected
  })
})

const openClassPopup = () => {
  showClassPopup.value = true
  classDisplayText.value = ''
  classSearchKeyword.value = ''
}

const closeClassPopup = () => {
  showClassPopup.value = false
  classSearchKeyword.value = ''
  classDisplayText.value = selectedClasses.value.length > 0 ? `已选择${selectedClasses.value.length}个班级` : ''
}

// --- 表单校验错误状态（视觉反馈） ---
const coverError = ref(false)
const wordError = ref(false)
const coverShaking = ref(false)
const wordShaking = ref(false)
const courseNameError = ref(false)
const courseNameShaking = ref(false)

const newCourseForm = reactive({
  cover: [],
  course_name: '',
  wordFile: null,
  wordMarkdown: ''
})

// ==================== 请求取消与防抖机制 ====================
let abortController = null

/**
 * 获取课程数据
 * 【规范遵循说明】
 * 1. 不使用 try-catch 包裹，HTTP 错误交由全局拦截器。
 * 2. 直接解构 res.data.courses，不写 || [] 防御性兜底。
 * 3. 针对网络请求取消，使用 .catch(() => {}) 静默吞没，符合规范中“网络本身断开”的特例许可。
 * 4. 图片资源严格通过环境变量拼接后端返回的相对路径，禁止硬编码或直接渲染后端相对路径。
 */
const fetchCourses = async (isAppend = false) => {
  if (!isAppend) {
    loading.value = true
    courseList.value = []
    pagination.page = 1
    if (scrollContainerRef.value) scrollContainerRef.value.scrollTop = 0
  } else {
    if (!pagination.hasMore) return
    loadingMore.value = true
  }

  if (abortController) abortController.abort()
  abortController = new AbortController()
  const signal = abortController.signal

  const res = await get_teacher_courses(pagination.page, signal).catch(() => {})

  if (!res) {
    loading.value = false
    loadingMore.value = false
    return
  }

  const { courses } = res.data

  const mapped = courses.map(course => ({
    id: course.course_id,
    name: course.course_name,
    cover: `${import.meta.env.VITE_RESOURCE_BASE_URL}${course.course_cover}`,
    teacher: teacherName.value
  }))

  if (isAppend) {
    courseList.value.push(...mapped)
  } else {
    courseList.value = mapped
  }

  pagination.hasMore = mapped.length >= 16
  loading.value = false
  loadingMore.value = false
}


/** 滚动触发加载 */
const handleScroll = (e) => {
  const { scrollTop, clientHeight, scrollHeight } = e.target
  if (scrollHeight - scrollTop - clientHeight < 100) {
    if (!loadingMore.value && !loading.value && pagination.hasMore) {
      pagination.page += 1
      fetchCourses(true)
    }
  }
}

/** 跳转课程编辑页 */
const goToCourseEdit = (courseId) => {
  router.push(`/teacher/course/${courseId}`)
}

// ==================== 模态框逻辑 ====================
const openCreateModal = () => {
  parseAborted = false
  showCreateModal.value = true
  selectedClasses.value = []
  showClassPopup.value = false
  coverError.value = false
  wordError.value = false
  courseNameError.value = false
  fetchClassList()
  document.addEventListener('click', handleDocumentClick)
}

const closeCreateModal = () => {
  parseAborted = true
  showCreateModal.value = false
  parsingWord.value = false
  wordFileName.value = ''
  showClassPopup.value = false
  selectedClasses.value = []
  classDisplayText.value = ''
  classSearchKeyword.value = ''
  newCourseForm.cover = []
  newCourseForm.course_name = ''
  newCourseForm.wordFile = null
  newCourseForm.wordMarkdown = ''
  coverError.value = false
  wordError.value = false
  courseNameError.value = false
  document.removeEventListener('click', handleDocumentClick)
}

const onCoverRead = (file) => {
  // 纯事件回调，无逻辑处理
}

// ==================== 学习班级：获取列表与弹窗交互 ====================
const fetchClassList = async () => {
  classListLoading.value = true
  // 直接 await，错误交由全局拦截
  const res = await get_all_classes()

  // 严格遵循信封与底线：直接解构 data.classes，禁止 || []
  const { classes } = res.data
  classList.value = classes.map((item, index) => ({
    id: index + 1,
    class_name: item.class_name
  }))

  classListLoading.value = false
}

const toggleClassPopup = () => {
  showClassPopup.value ? closeClassPopup() : openClassPopup()
}

const handleDocumentClick = (e) => {
  if (showClassPopup.value && classSelectRef.value && !classSelectRef.value.contains(e.target)) {
    closeClassPopup()
  }
}

// ==================== Word 文档上传与解析 ====================
const triggerWordUpload = () => {
  if (parsingWord.value) return
  wordInputRef.value?.click()
}

const onWordFileChange = (e) => {
  const file = e.target.files[0]
  if (!file) return
  parseAborted = true
  wordFileName.value = file.name
  newCourseForm.wordFile = file
  e.target.value = ''
  wordError.value = false
  parseWordToMarkdown(file)
}

const parseWordToMarkdown = async (file) => {
  parseAborted = false
  parsingWord.value = true
  try {
    const arrayBuffer = await file.arrayBuffer()
    if (parseAborted) return
    const result = await mammoth.convertToHtml({ arrayBuffer })
    if (parseAborted) return
    const turndown = new TurndownService()
    const markdown = turndown.turndown(result.value)
    if (parseAborted) return
    newCourseForm.wordMarkdown = markdown
    wordError.value = false
    // 前端自定义成功文案，不读后端 message
    showToast({ message: '教案解析完成', type: 'success' })
  } catch (error) {
    if (!parseAborted) {
      // 本地文件解析异常属于纯前端逻辑错误，可按需提示，不涉及 HTTP 状态码红线
      showToast({ message: '文档解析失败，请检查文件格式', type: 'fail' })
    }
  } finally {
    parsingWord.value = false
  }
}

// ==================== 提交创建课程 ====================
const submitCreateCourse = async () => {
  if (parsingWord.value) return

  coverError.value = false
  wordError.value = false
  courseNameError.value = false
  let isValid = true

  if (!newCourseForm.course_name.trim()) {
    courseNameError.value = true
    courseNameShaking.value = true
    setTimeout(() => { courseNameShaking.value = false }, 400)
    isValid = false
  }

  if (!newCourseForm.cover.length || !newCourseForm.cover[0]?.file) {
    coverError.value = true
    coverShaking.value = true
    setTimeout(() => { coverShaking.value = false }, 400)
    isValid = false
  }

  if (!newCourseForm.wordFile || !newCourseForm.wordMarkdown) {
    wordError.value = true
    wordShaking.value = true
    setTimeout(() => { wordShaking.value = false }, 400)
    isValid = false
  }

  if (!isValid) return

  // 直接 await，不包裹 try-catch。只要不抛错走到下面，说明绝对成功
  await create_new_course(
    newCourseForm.cover[0]?.file,
    newCourseForm.course_name,
    JSON.stringify(selectedClasses.value),
    newCourseForm.wordMarkdown
  )

  // 前端自定义成功提示文案
  showToast({ message: '课程创建成功', type: 'success' })
  closeCreateModal()
  fetchCourses(false)
}

const clearCourseNameError = () => {
  courseNameError.value = false
}

// ==================== 生命周期 ====================
onMounted(() => fetchCourses(false))

onBeforeUnmount(() => {
  if (abortController) abortController.abort()
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<style scoped src="../../styles/views/teacher/ResourceManage.css"></style>
