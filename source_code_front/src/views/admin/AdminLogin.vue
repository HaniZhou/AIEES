<template>
  <div class="admin-login-wrapper page-fade-enter">
    <div class="glass-overlay"></div>
    <div class="admin-login-card">
      <h1 class="admin-login-title">管理员登录</h1>

      <div class="login-form">
        <div class="form-item-wrapper" :class="{ 'has-error': errors.accountId, 'shake': shaking.accountId }">
          <van-field v-model="form.accountId" label="账号" placeholder="请输入管理员账号" :border="false" @focus="clearError('accountId')"/>
          <div class="error-msg" v-if="errors.accountId">{{ errorMsgs.accountId }}</div>
        </div>

        <div class="form-item-wrapper" :class="{ 'has-error': errors.password, 'shake': shaking.password }">
          <van-field v-model="form.password" :type="showPassword ? 'text' : 'password'" label="密码" placeholder="请输入密码" :border="false" @focus="clearError('password')">
            <template #right-icon>
              <van-icon v-if="form.password" :name="showPassword ? 'eye-o' : 'closed-eye'" class="field-pwd-icon" @click="togglePasswordVisible"/>
            </template>
          </van-field>
          <div class="error-msg" v-if="errors.password">{{ errorMsgs.password }}</div>
        </div>

        <div v-if="showCaptcha" class="form-item-wrapper" :class="{ 'has-error': errors.captcha, 'shake': shaking.captcha }">
          <div class="captcha-layout">
            <span class="captcha-label">验证码</span>
            <img :src="captchaImage" @click="fetchCaptcha" class="captcha-img" alt="验证码"/>
            <input v-model="captchaCode" type="text" class="captcha-input" placeholder="请输入计算结果" @focus="clearError('captcha')"/>
          </div>
          <div class="error-msg" v-if="errors.captcha">{{ errorMsgs.captcha }}</div>
        </div>
      </div>

      <div class="admin-action-group">
        <button class="admin-btn-login" @click="handleLogin" :disabled="loading || isLocked">
          <span v-if="!loading">{{ isLocked ? `请 ${lockMinutes} 分钟后重试` : '登录' }}</span>
          <van-loading v-else type="spinner" size="24px" color="#fff"/>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { getCaptcha } from "@/api/utils.js"
import { adminAuth } from "@/api/admin.js"

const router = useRouter()

const form = reactive({ accountId: '', password: '' })
const errors = reactive({ accountId: false, password: false, captcha: false })
const errorMsgs = reactive({ accountId: '', password: '', captcha: '' })
const shaking = reactive({ accountId: false, password: false, captcha: false })

const showCaptcha = ref(false)
const captchaImage = ref('')
const captchaKey = ref('')
const captchaCode = ref('')
const loading = ref(false)
const isLocked = ref(false)
const lockMinutes = ref(0)
const showPassword = ref(false)
let lockTimer = null

const togglePasswordVisible = () => {
  showPassword.value = !showPassword.value
}

const clearError = (field) => {
  errors[field] = false
  errorMsgs[field] = ''
}

const triggerError = (field, msg = '') => {
  errors[field] = true
  errorMsgs[field] = msg
  shaking[field] = false
  requestAnimationFrame(() => {
    shaking[field] = true
    setTimeout(() => {
      shaking[field] = false
    }, 450)
  })
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

const handleLogin = async () => {
  let isValid = true
  if (!form.accountId.trim()) { triggerError('accountId', '不能为空'); isValid = false; }
  if (!form.password.trim()) { triggerError('password', '不能为空'); isValid = false; }
  if (showCaptcha.value && !captchaCode.value.trim()) { triggerError('captcha', '不能为空'); isValid = false; }

  if (!isValid || isLocked.value) return

  const payload = {
    id: form.accountId.trim(),
    password: form.password.trim(),
    role: "admin"
  }

  if (showCaptcha.value) {
    payload.captcha_key = captchaKey.value
    payload.captcha_code = captchaCode.value.trim()
  }

  loading.value = true

  const res = await adminAuth(payload, { skipToast: true }).catch((err) => {
    loading.value = false
    if (err.response?.data) {
      return err.response.data
    }
    return null
  })

  if (!res) return

  if (res.code === 200) {
    const { access_token } = res.data
    const { username, id } = res.data.user
    localStorage.setItem('token', access_token)
    localStorage.setItem('role', 'admin')
    localStorage.setItem('username', username)
    localStorage.setItem('id', id)

    showCaptcha.value = false
    captchaCode.value = ''
    if (lockTimer) {
      clearInterval(lockTimer)
      lockTimer = null
    }
    isLocked.value = false

    await router.push('/admin/manage')
  } else {
    const errorPayload = res.data

    if (res.code === 423 && errorPayload.locked) {
      isLocked.value = true
      lockMinutes.value = Math.ceil((errorPayload.lock_ttl || 900) / 60)
      showCaptcha.value = false
      startLockCountdown()
      triggerError('password', res.message)
    } else if (res.code === 403 && errorPayload.need_captcha) {
      showCaptcha.value = true
      fetchCaptcha()
      triggerError('captcha', res.message)
    } else if (res.code === 400) {
      fetchCaptcha()
      triggerError('captcha', res.message)
    } else if (errorPayload.need_captcha) {
      showCaptcha.value = true
      fetchCaptcha()
      triggerError('password', res.message)
    } else {
      triggerError('accountId')
      triggerError('password', res.message || '登录失败，请检查账号或密码')
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

<style scoped src="../../styles/views/admin/AdminLogin.css"></style>