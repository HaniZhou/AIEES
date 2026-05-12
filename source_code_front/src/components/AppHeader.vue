<!-- template 部分保持不变 -->
<template>
  <header class="app-header">
    <!-- 左侧 Logo 区域 -->
    <div class="logo-area" @click="goHome">
      <span class="logo-text">启思智伴</span>
    </div>

    <!-- 中间导航菜单区域 -->
    <nav class="nav-menu">
      <ul class="menu-list">
        <li v-for="item in currentMenu" :key="item.path" :class="['menu-item', { active: isActive(item.path) }]" @click="navigate(item.path)">
          {{ item.name }}
        </li>
      </ul>
    </nav>

    <!-- 右侧个人信息入口与下拉菜单 -->
    <div class="user-info-area" @click.stop="toggleDropdown">
      <div class="user-profile">
        <van-image round src="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg" class="user-avatar" />
        <span class="user-name">{{ userName }}</span>
        <van-icon name="arrow-down" class="dropdown-icon" :class="{ 'is-open': showDropdown }" />
      </div>

      <transition name="dropdown-fade">
        <div class="user-dropdown" v-if="showDropdown" @click.stop>
          <div class="dropdown-item" @click="openPwdModal">
            <van-icon name="edit" size="16" />
            <span>修改密码</span>
          </div>
          <div class="dropdown-divider"></div>
          <div class="dropdown-item text-danger" @click="handleLogout">
            <van-icon name="revoke" size="16" />
            <span>退出登录</span>
          </div>
        </div>
      </transition>
    </div>

    <!-- 修改密码模态框 -->
    <teleport to="body">
      <transition name="modal-fade">
        <div class="pwd-modal-overlay" v-if="showPwdModal" @click.self="closePwdModal">
          <div class="pwd-modal-card">
            <h2 class="pwd-modal-title">修改密码</h2>

            <!-- 原密码 -->
            <div class="form-item-wrapper" :class="{ 'has-error': pwdErrors.oldPwd, 'shake': pwdShaking.oldPwd }">
              <van-field
                v-model="pwdForm.oldPwd"
                type="password"
                label="原密码"
                placeholder="请输入原密码"
                :border="false"
                clearable
                @focus="clearError('oldPwd')"
              />
              <div class="error-msg" v-if="pwdErrors.oldPwd">{{ errorMsgText }}</div>
            </div>

            <!-- 新密码 -->
            <div class="form-item-wrapper" :class="{ 'has-error': pwdErrors.newPwd, 'shake': pwdShaking.newPwd }">
              <van-field
                v-model="pwdForm.newPwd"
                type="password"
                label="新密码"
                placeholder="请输入新密码"
                :border="false"
                clearable
                @focus="clearError('newPwd')"
              />
              <div class="error-msg" v-if="pwdErrors.newPwd">新密码不能为空</div>
            </div>

            <!-- 确认密码 -->
            <div class="form-item-wrapper" :class="{ 'has-error': pwdErrors.confirmPwd, 'shake': pwdShaking.confirmPwd }">
              <van-field
                v-model="pwdForm.confirmPwd"
                type="password"
                label="确认密码"
                placeholder="请再次输入新密码"
                :border="false"
                clearable
                @focus="clearError('confirmPwd')"
              />
              <div class="error-msg" v-if="pwdErrors.confirmPwd">两次输入的密码不一致</div>
            </div>

            <!-- 底部按钮组 -->
            <div class="pwd-action-group">
              <button class="btn btn-cancel" @click="closePwdModal" :disabled="loading">取消</button>
              <button class="btn btn-confirm" @click="submitPwdChange" :disabled="loading">
                <span v-if="!loading">确定</span>
                <van-loading v-else type="spinner" size="20px" color="#fff" />
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>
  </header>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
// 引入 API
import { updatePassword } from '../api/utils'

// === 接收 Prop ===
const props = defineProps({
  role: {
    type: String,
    required: true,
    validator: (value) => ['student', 'teacher', 'admin'].includes(value)
  },
  userName: {
    type: String,
    default: '测试用户'
  }
})

const router = useRouter()
const route = useRoute()

// === 导航菜单逻辑 ===
const menus = {
  student: [
    { name: '首页', path: '/index' },
    { name: '学习中心', path: '/resources' }
  ],
  teacher: [
    { name: '首页', path: '/teacher/index' },
    { name: '课程管理', path: '/teacher/resources' }
  ],
  admin: [
    { name: '组织与用户管理', path: '/admin/manage' }
  ]
}

const currentMenu = computed(() => menus[props.role] || [])
const isActive = (path) => route.path.startsWith(path)

const navigate = (path) => {
  if (route.path !== path) router.push(path)
}

const goHome = () => {
  let homePath = '/index'
  if (props.role === 'teacher') homePath = '/teacher/index'
  if (props.role === 'admin') homePath = '/admin/manage'
  navigate(homePath)
}

// === 下拉菜单逻辑 ===
const showDropdown = ref(false)
const toggleDropdown = () => {
  showDropdown.value = !showDropdown.value
}

const closeDropdownOutside = () => {
  showDropdown.value = false
}

onMounted(() => {
  document.addEventListener('click', closeDropdownOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', closeDropdownOutside)
})

// === 退出登录逻辑 ===
const handleLogout = () => {
  showDropdown.value = false
  showConfirmDialog({
    title: '退出登录',
    message: '确定要退出当前账号吗？',
  }).then(() => {
    localStorage.clear()
    showToast('已安全退出')
    window.location.href='/'
  }).catch(() => {})
}

// === 修改密码模态框逻辑 ===
const showPwdModal = ref(false)
const loading = ref(false)
const errorMsgText = ref('') // 用于显示后端返回的具体错误信息

const pwdForm = reactive({
  oldPwd: '',
  newPwd: '',
  confirmPwd: ''
})

const pwdErrors = reactive({
  oldPwd: false,
  newPwd: false,
  confirmPwd: false
})

const pwdShaking = reactive({
  oldPwd: false,
  newPwd: false,
  confirmPwd: false
})

const openPwdModal = () => {
  showDropdown.value = false
  pwdForm.oldPwd = ''
  pwdForm.newPwd = ''
  pwdForm.confirmPwd = ''
  Object.keys(pwdErrors).forEach(k => pwdErrors[k] = false)
  errorMsgText.value = ''
  showPwdModal.value = true
}

const closePwdModal = () => {
  if (!loading.value) {
    showPwdModal.value = false
  }
}

const clearError = (field) => {
  pwdErrors[field] = false
}

const triggerError = (field, msg = '不能为空') => {
  if (field === 'oldPwd') errorMsgText.value = msg
  pwdErrors[field] = true
  pwdShaking[field] = true
  setTimeout(() => {
    pwdShaking[field] = false
  }, 400)
}

const submitPwdChange = async () => {
  // 1. 前端基础非空与一致性校验
  let isValid = true
  if (!pwdForm.oldPwd.trim()) {
    triggerError('oldPwd', '原密码不能为空')
    isValid = false
  }
  if (!pwdForm.newPwd.trim()) {
    triggerError('newPwd', '新密码不能为空')
    isValid = false
  }
  if (!pwdForm.confirmPwd.trim()) {
    triggerError('confirmPwd', '请确认新密码')
    isValid = false
  }
  if (isValid && pwdForm.newPwd !== pwdForm.confirmPwd) {
    triggerError('confirmPwd', '两次输入的密码不一致')
    isValid = false
  }
  if (!isValid) return

  // 2. 调用后端接口
  loading.value = true
  try {
    const res = await updatePassword({
      old_password: pwdForm.oldPwd,
      new_password: pwdForm.newPwd,
      confirm_password: pwdForm.confirmPwd // 修复缺失字段，避免后端校验报 Field required
    })

    // 3. 严格根据后端契约，只有业务 code 为 200 时才算成功修改
    if (res.code === 200) {
      showToast({ message: '密码修改成功', type: 'success' })
      showPwdModal.value = false
      // 按需求：成功修改后不退出登录
    } else {
      // 业务失败（如原密码错误等），直接使用后端返回的 message，严禁前端硬编码兜底
      const errMsg = res.message
      if (errMsg && errMsg.includes('原密码')) {
        triggerError('oldPwd', errMsg)
      } else {
        showToast(errMsg)
      }
    }
  } catch (error) {
    // HTTP 层异常或拦截器抛出的业务异常
    // 遵循规范：全局拦截器已统一 Toast 提示，组件内仅需处理特定的 UI 联动（原密码输入框标红）
    const errMsg = error?.response?.data?.message || error?.message
    if (errMsg && errMsg.includes('原密码')) {
      triggerError('oldPwd', errMsg)
    }
  } finally {
    loading.value = false
  }
}

</script>

<!-- 严格遵守样式隔离原则，仅引入独立 CSS -->
<style scoped src="../styles/components/AppHeader.css"></style>