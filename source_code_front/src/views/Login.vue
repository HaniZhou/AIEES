<template>
  <div class="login-wrapper page-fade-enter">
    <!-- 1. 背景层：多彩气泡轻轻晃动 (带有模糊表情) -->
    <div class="bubbles-bg">
      <div class="bubble b1">
        <div class="b-face"><div class="b-eye l"></div><div class="b-eye r"></div><div class="b-mouth-straight"></div></div>
      </div>
      <div class="bubble b2">
        <div class="b-face"><div class="b-eye l"></div><div class="b-eye r"></div><div class="b-mouth-o"></div></div>
      </div>
      <div class="bubble b3">
        <div class="b-face"><div class="b-eye l"></div><div class="b-eye r"></div><div class="b-mouth-smile"></div></div>
      </div>
      <div class="bubble b4">
        <div class="b-face"><div class="b-eye l"></div><div class="b-eye r"></div><div class="b-mouth-straight"></div></div>
      </div>
      <div class="bubble b5">
        <div class="b-face"><div class="b-eye l"></div><div class="b-eye r"></div><div class="b-mouth-o"></div></div>
      </div>
    </div>

    <!-- 2. 登录卡片容器 -->
    <div class="login-card">
      <h1 class="login-title">用户登录</h1>

      <!-- 3. 表单区域 -->
      <div class="login-form">
        <!-- 学校选择框 -->
        <div class="form-item-wrapper" :class="{ 'has-error': errors.organization, 'shake': shaking.organization }">
          <van-field v-model="form.orgName" label="学校" placeholder="请选择学校" :border="false" readonly is-link
                     @click="openOrgPopup"/>
          <div class="error-msg" v-if="errors.organization">请选择学校</div>
        </div>

        <!-- 账号输入框 -->
        <div class="form-item-wrapper" :class="{ 'has-error': errors.accountId, 'shake': shaking.accountId }">
          <van-field v-model="form.accountId" :label="is_stu ? '学号' : '工号'"
                     :placeholder="`请输入${is_stu ? '学号' : '工号'}`" :border="false" clearable
                     @focus="clearError('accountId')"/>
          <div class="error-msg" v-if="errors.accountId">不能为空</div>
        </div>

        <!-- 密码输入框 (增加了 focus 和 blur 事件来控制大黄脸闭眼) -->
        <div class="form-item-wrapper" :class="{ 'has-error': errors.password, 'shake': shaking.password }">
          <van-field v-model="form.password" type="password" label="密码" placeholder="请输入密码" :border="false"
                     clearable @focus="handlePasswordFocus" @blur="isPasswordFocused = false"/>
          <div class="error-msg" v-if="errors.password">不能为空</div>
        </div>

        <!-- 验证码区域 -->
        <div v-if="showCaptcha" class="form-item-wrapper"
             :class="{ 'has-error': errors.captcha, 'shake': shaking.captcha }">
          <div class="captcha-layout">
            <span class="captcha-label">验证码</span>
            <img :src="captchaImage" @click="fetchCaptcha" class="captcha-img" alt="验证码"/>
            <input
                v-model="captchaCode"
                type="text"
                class="captcha-input"
                placeholder="请输入计算结果"
                @focus="clearError('captcha')"
            />
          </div>
          <div class="error-msg" v-if="errors.captcha">不能为空</div>
        </div>

      </div>

      <!-- 4. 底部按钮组 -->
      <div class="action-group">
        <button class="btn btn-switch" @click="switchRole" :disabled="loading">
          {{ is_stu ? '切换至教师登录' : '切换至学生登录' }}
        </button>
        <button class="btn btn-login" @click="handleLogin" :disabled="loading || isLocked">
          <span v-if="!loading">{{ isLocked ? `请 ${lockMinutes} 分钟后重试` : '登录' }}</span>
          <van-loading v-else type="spinner" size="24px" color="#fff"/>
        </button>
      </div>
    </div>

    <!-- 右下角黄色大表情气球 -->
    <div class="mascot-container">
      <!-- 失焦模糊的黄色大气球 -->
      <div class="mascot-head" :class="{ 'is-sleeping': isPasswordFocused }">
        <div class="face">
          <div class="eye left"></div>
          <div class="eye right"></div>
          <div class="mouth"></div>
        </div>
      </div>
    </div>

    <!-- 5. 学校选择弹窗 -->
    <van-popup v-model:show="showOrgPopup" position="center" round overlay-class="org-popup-overlay"
               @open="onPopupOpen">
      <div class="org-popup-content">
        <div class="org-popup-header">选择学校</div>
        <div class="org-search-wrapper">
          <van-search v-model="orgSearchKeyword" placeholder="搜索学校名称" shape="round"
                      @update:model-value="handleOrgSearch"/>
        </div>
        <div class="org-list-wrapper" ref="orgListRef" @scroll="handleOrgScroll">
          <div v-for="item in orgList" :key="item.organization_id" class="org-list-item"
               :class="{ active: form.orgObj && form.orgObj.organization_id === item.organization_id }"
               @click="selectOrg(item)">
            {{ item.organization_name }}
          </div>
          <div v-if="orgLoading" class="org-list-status">
            <van-loading type="spinner" size="20px"/>
          </div>
          <div v-if="orgFinished && orgList.length > 0" class="org-list-status">没有更多了</div>
          <div v-if="!orgLoading && orgList.length === 0 && orgSearched" class="org-list-status">暂无匹配学校</div>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, reactive, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { auth, getOrganizations, getCaptcha } from "@/api/utils.js"

const router = useRouter()

// --- 登录表单状态管理 ---
const is_stu = ref(true)
const loading = ref(false)
const isPasswordFocused = ref(false)

const form = reactive({
  orgObj: null,
  orgName: '',
  accountId: '',
  password: '',
})
const errors = reactive({
  organization: false,
  accountId: false,
  password: false,
  captcha: false
})
const shaking = reactive({
  organization: false,
  accountId: false,
  password: false,
  captcha: false
})

// --- 验证码与锁定状态管理 ---
const showCaptcha = ref(false)
const captchaImage = ref('')
const captchaKey = ref('')
const captchaCode = ref('')
const isLocked = ref(false)
const lockMinutes = ref(0)
let lockTimer = null

const switchRole = () => {
  if (loading.value) return
  form.accountId = ''
  form.password = ''
  form.orgObj = null
  form.orgName = ''
  captchaCode.value = ''
  Object.keys(errors).forEach(key => {
    errors[key] = false
    shaking[key] = false
  })
  is_stu.value = !is_stu.value
}

const clearError = (field) => {
  errors[field] = false
}

const triggerError = (field) => {
  errors[field] = true
  shaking[field] = true
  setTimeout(() => {
    shaking[field] = false
  }, 400)
}

const handlePasswordFocus = () => {
  clearError('password')
  isPasswordFocused.value = true
}

const fetchCaptcha = async () => {
  const res = await getCaptcha().catch(() => {})
  if (!res) return
  captchaKey.value = res.data.captcha_key
  captchaImage.value = res.data.captcha_image
}

const startLockCountdown = () => {
  if (lockTimer) clearInterval(lockTimer)
  lockTimer = setInterval(() => {
    if (lockMinutes.value <= 1) {
      clearInterval(lockTimer)
      lockTimer = null
      isLocked.value = false
    } else {
      lockMinutes.value--
    }
  }, 60000)
}

// --- 机构列表状态与逻辑 ---
const showOrgPopup = ref(false)
const orgSearchKeyword = ref('')
const orgList = ref([])
const orgLoading = ref(false)
const orgFinished = ref(false)
const orgSearched = ref(false)
const orgPage = ref(1)
const orgListRef = ref(null)

const debounce = (fn, delay) => {
  let timer = null
  return (...args) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, args), delay)
  }
}

const fetchOrgList = async (isRefresh = false) => {
  if (orgLoading.value) return
  if (isRefresh) {
    orgPage.value = 1
    orgFinished.value = false
    orgSearched.value = false
  }
  orgLoading.value = true
  const res = await getOrganizations(orgPage.value, orgSearchKeyword.value).catch(() => {
    orgLoading.value = false
  })
  if (!res) return
  const { list } = res.data
  if (isRefresh) {
    orgList.value = list
  } else {
    orgList.value.push(...list)
  }
  orgSearched.value = true
  if (list.length < 30) {
    orgFinished.value = true
  }
  orgLoading.value = false
}

const onPopupOpen = () => {
  orgSearchKeyword.value = ''
  fetchOrgList(true)
}

const handleOrgSearch = debounce(() => {
  fetchOrgList(true)
}, 300)

const handleOrgScroll = () => {
  if (!orgListRef.value || orgLoading.value || orgFinished.value) return
  const { scrollTop, scrollHeight, clientHeight } = orgListRef.value
  if (scrollHeight - scrollTop - clientHeight < 50) {
    orgPage.value++
    fetchOrgList(false)
  }
}

const selectOrg = (item) => {
  form.orgObj = item
  form.orgName = item.organization_name
  errors.organization = false
  showOrgPopup.value = false
}

const openOrgPopup = () => {
  clearError('organization')
  showOrgPopup.value = true
}

const handleLogin = async () => {
  let isValid = true
  if (!form.orgObj) {
    triggerError('organization')
    isValid = false
  }
  if (!form.accountId || form.accountId.trim() === '') {
    triggerError('accountId')
    isValid = false
  }
  if (!form.password || form.password.trim() === '') {
    triggerError('password')
    isValid = false
  }
  if (showCaptcha.value && (!captchaCode.value || captchaCode.value.trim() === '')) {
    triggerError('captcha')
    isValid = false
  }

  if (!isValid || isLocked.value) return

  const rawId = form.accountId.trim()
  const password = form.password.trim()
  const role = is_stu.value ? "student" : "teacher"
  const finalAccountId = `${form.orgObj.prefix}${rawId}`

  const payload = {
    id: finalAccountId,
    password,
    role
  }

  if (showCaptcha.value) {
    payload.captcha_key = captchaKey.value
    payload.captcha_code = captchaCode.value.trim()
  }

  loading.value = true

  const res = await auth(payload).catch((err) => {
    loading.value = false
    if (err.response?.data) {
      return err.response.data
    }
    return null
  })

  if (!res) return

  if (res.code === 200) {
    const { access_token } = res.data
    const { role: resRole, username, id, student_class: user_class } = res.data.user
    localStorage.setItem('token', access_token)
    localStorage.setItem('role', resRole)
    localStorage.setItem('username', username)
    localStorage.setItem('user_class', user_class)
    localStorage.setItem('id', rawId)
    localStorage.setItem('is_first_show', true)

    showCaptcha.value = false
    captchaCode.value = ''
    if (lockTimer) {
      clearInterval(lockTimer)
      lockTimer = null
    }
    isLocked.value = false

    await router.push(resRole === 'student' ? '/index' : '/teacher/index')
  } else {
    showToast(res.message)
    const errorPayload = res.data

    if (res.code === 423 && errorPayload.locked) {
      isLocked.value = true
      lockMinutes.value = Math.ceil((errorPayload.lock_ttl || 900) / 60)
      showCaptcha.value = false
      startLockCountdown()
    } else if (errorPayload.need_captcha) {
      showCaptcha.value = true
      fetchCaptcha()
    }

    if (res.code === 400) {
      fetchCaptcha()
    }
  }

  loading.value = false
}

onBeforeUnmount(() => {
  if (lockTimer) {
    clearInterval(lockTimer)
    lockTimer = null
  }
})
</script>

<style scoped src="../styles/views/Login.css"></style>