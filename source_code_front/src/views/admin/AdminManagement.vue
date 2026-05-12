<template>
  <div class="admin-layout">
    <AppHeader role="admin" :userName="adminName" />
    <header class="admin-header">
      <span>系统管理后台</span>
    </header>
    <main class="admin-main">
      <!-- 左侧面板：组织管理 -->
      <aside class="left-panel">
        <div class="left-panel-title">
          <span>组织管理</span>
          <van-icon name="plus" color="var(--color-primary)" cursor="pointer" @click="openOrgModal('add')" />
        </div>
        <div class="org-search-box">
          <van-icon name="search" class="search-icon" />
          <input type="text" v-model="orgKeyword" placeholder="搜索组织" @input="debouncedOrgSearch" />
        </div>
        <div class="org-list">
          <div v-for="org in orgList" :key="org.organization_id" class="org-list-item" :class="{ 'is-active': selectedOrg?.organization_id === org.organization_id }" @click="handleOrgSelect(org)">
            <span class="org-item-name">{{ org.organization_name }}</span>
            <span class="phase-pill" :class="org.phase">{{ getPhaseName(org.phase) }}</span>
          </div>
          <van-empty v-if="!orgLoading && orgList.length === 0" description="暂无组织" image-size="60" />
          <div class="scroll-load-indicator" v-if="orgLoading">加载中...</div>
        </div>
      </aside>

      <!-- 右侧内容区 -->
      <section class="right-content">
        <template v-if="selectedOrg">
          <!-- 组织信息栏 -->
          <div class="org-info-bar">
            <div class="org-info-left">
              <span class="org-info-name">{{ selectedOrg.organization_name }}</span>
              <span class="org-info-prefix">前缀：{{ selectedOrg.prefix || '无' }}</span>
              <van-icon name="edit" class="class-action-icon edit" @click="openOrgModal('edit', selectedOrg)" />
            </div>
            <button class="btn-delete-org" @click="handleDeleteOrg">删除组织</button>
          </div>

          <!-- Tab栏 -->
          <div class="view-tab-bar" v-if="!classDetailView">
            <div class="view-tab-item" :class="{ 'is-active': activeTab === 'class' }" @click="activeTab = 'class'"> 班级管理</div>
            <div class="view-tab-item" :class="{ 'is-active': activeTab === 'teacher' }" @click="activeTab = 'teacher'"> 教师管理</div>
          </div>

          <!-- ================= 视图 A：班级列表 ================= -->
          <div class="content-scroll" ref="classListRef" @scroll="handleClassScroll" v-if="!classDetailView && activeTab === 'class'">
            <div class="toolbar">
              <div class="toolbar-search">
                <van-icon name="search" color="var(--color-text-placeholder)" />
                <input v-model="classKeyword" placeholder="搜索班级名称" @input="debouncedClassSearch" />
              </div>
              <button class="btn-add" @click="openClassModal('add')"><van-icon name="plus" /> 添加班级</button>
            </div>
            <div class="class-list-container">
              <div v-for="cls in classList" :key="cls.class_id" class="class-list-item" @click="handleClassClick(cls)">
                <span class="class-list-item-name">{{ cls.class_name }}</span>
                <div class="class-list-item-actions">
                  <van-icon name="edit" class="class-action-icon edit" @click.stop="openClassModal('edit', cls)" />
                  <van-icon name="delete" class="class-action-icon delete" @click.stop="handleDeleteClassIcon(cls)" />
                </div>
              </div>
            </div>
            <div class="scroll-load-indicator" v-if="classLoading">加载中...</div>
            <div class="scroll-load-indicator" v-if="!classLoading && !classHasMore && classList.length > 0">没有更多了</div>
            <van-empty v-if="!classLoading && classList.length === 0" description="暂无班级" image-size="80" />
          </div>

          <!-- ================= 视图 B：班级详情与学生管理 ================= -->
          <div class="content-scroll" ref="studentTableRef" @scroll="handleStudentScroll" v-if="classDetailView">
            <!-- 面包屑与头部操作 -->
            <div class="class-detail-nav">
              <button class="btn-back" @click="handleBackToClasses"><van-icon name="arrow-left" /> 返回班级列表</button>
              <span class="class-detail-nav-title">班级详情</span>
              <button class="btn-delete-class" @click="handleDeleteClass">删除班级</button>
            </div>

            <!-- 班级信息卡片 -->
            <div class="class-info-card">
              <div class="class-info-field">
                <span class="class-info-label">班级名称</span>
                <div style="display: flex; align-items: center;">
                  <input type="text" class="class-info-input" :class="{ 'has-error': classNameError }" v-model="classNameEditing" @blur="handleClassNameBlur" />
                  <span class="class-info-saving" v-if="classNameSaving">保存中...</span>
                </div>
              </div>
              <div class="class-info-field">
                <span class="class-info-label">所属组织</span>
                <span class="class-info-readonly">{{ selectedOrg.organization_name }}</span>
              </div>
              <div class="class-info-field">
                <span class="class-info-label">学生人数</span>
                <span class="class-info-value">{{ classStudentCount }} 人</span>
              </div>
            </div>

            <!-- Excel 导入面板 -->
            <div v-if="importMode" class="import-panel">
              <div class="upload-area" :class="{ 'has-file': importFile }" @click="$refs.fileInput.click()" @dragover.prevent @drop="handleFileDrop">
                <van-icon name="photograph" class="upload-icon" />
                <span class="upload-text">{{ importFile ? importFile.name : '点击或拖拽 Excel 文件到此处' }}</span>
                <span class="upload-hint" v-if="!importFile">支持 .xlsx, .xls 格式，第一列为学号，第二列为姓名</span>
                <input type="file" ref="fileInput" style="display: none" accept=".xlsx, .xls" @change="handleFileSelect" />
              </div>
              <table class="import-preview-table" v-if="importData.length > 0">
                <thead>
                  <tr>
                    <th>学号</th>
                    <th>姓名</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in importData" :key="row.id" :class="{ 'row-error': !row.isValid }">
                    <td>{{ row.id }}</td>
                    <td>{{ row.username }}</td>
                    <td>
                      <span v-if="row.isValid" style="color: #67C23A">验证通过</span>
                      <span v-else class="row-error-text">{{ row.errorMsg }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div class="import-actions" v-if="importFile">
                <button class="btn-cancel-action" @click="handleCancelImport">取消</button>
                <button class="btn-confirm-import" @click="handleConfirmImport" :disabled="importSubmitting">
                  {{ importSubmitting ? '导入中...' : '确认导入' }}
                </button>
              </div>
            </div>

            <!-- 学生列表容器 -->
            <template v-else>
              <div class="student-toolbar">
                <div class="student-toolbar-left">
                  <div class="toolbar-search">
                    <van-icon name="search" color="var(--color-text-placeholder)" />
                    <input v-model="studentKeyword" placeholder="搜索学号/姓名" @input="debouncedStudentSearch" />
                  </div>
                </div>
                <div class="student-toolbar-right">
                  <button class="btn-import" @click="importMode = true"><van-icon name="description" /> 批量导入</button>
                  <button class="btn-add" @click="openStudentModal('add')"><van-icon name="plus" /> 添加学生</button>
                </div>
              </div>
              <div class="data-table-wrapper" v-if="studentList.length > 0">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>学号</th>
                      <th>姓名</th>
                      <th>班级</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="stu in studentList" :key="stu.id">
                      <td>{{ removePrefix(stu.id) }}</td>
                      <td>{{ stu.username }}</td>
                      <td class="td-readonly">{{ selectedClass.class_name }}</td>
                      <td>
                        <div class="table-actions">
                          <button class="table-action-btn edit" @click="openStudentModal('edit', stu)">编辑</button>
                          <button class="table-action-btn reset" @click="handleResetStudentPassword(stu)">重置密码</button>
                          <button class="table-action-btn delete" @click="handleDeleteStudent(stu)">删除</button>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="scroll-load-indicator" v-if="studentLoading">加载中...</div>
              <div class="scroll-load-indicator" v-if="!studentLoading && !studentHasMore && studentList.length > 0">没有更多了</div>
              <van-empty v-if="!studentLoading && studentList.length === 0" description="暂无学生数据" image-size="80" />
            </template>
          </div>

          <!-- ================= 视图 C：教师列表 ================= -->
          <div class="content-scroll" v-if="!classDetailView && activeTab === 'teacher'">
            <div class="toolbar">
              <div class="toolbar-search">
                <van-icon name="search" color="var(--color-text-placeholder)" />
                <input v-model="teacherKeyword" placeholder="搜索工号/姓名" @input="debouncedTeacherSearch" />
              </div>
              <div class="student-toolbar-right">
                <button class="btn-import" @click="teacherImportMode = true"><van-icon name="description" /> 批量导入</button>
                <button class="btn-add" @click="openTeacherModal('add')"><van-icon name="plus" /> 添加教师</button>
              </div>
            </div>

            <!-- 教师批量导入面板 -->
            <div v-if="teacherImportMode" class="import-panel">
              <div class="upload-area" :class="{ 'has-file': teacherImportFile }" @click="$refs.teacherFileInput.click()" @dragover.prevent @drop="handleTeacherFileDrop">
                <van-icon name="photograph" class="upload-icon" />
                <span class="upload-text">{{ teacherImportFile ? teacherImportFile.name : '点击或拖拽 Excel 文件到此处' }}</span>
                <span class="upload-hint" v-if="!teacherImportFile">支持 .xlsx, .xls 格式，第一列为工号，第二列为姓名</span>
                <input type="file" ref="teacherFileInput" style="display: none" accept=".xlsx, .xls" @change="handleTeacherFileSelect" />
              </div>
              <table class="import-preview-table" v-if="teacherImportData.length > 0">
                <thead>
                  <tr>
                    <th>工号</th>
                    <th>姓名</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in teacherImportData" :key="row.id" :class="{ 'row-error': !row.isValid }">
                    <td>{{ row.id }}</td>
                    <td>{{ row.username }}</td>
                    <td>
                      <span v-if="row.isValid" style="color: #67C23A">验证通过</span>
                      <span v-else class="row-error-text">{{ row.errorMsg }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div class="import-actions" v-if="teacherImportFile">
                <button class="btn-cancel-action" @click="handleCancelTeacherImport">取消</button>
                <button class="btn-confirm-import" @click="handleConfirmTeacherImport" :disabled="teacherImportSubmitting">
                  {{ teacherImportSubmitting ? '导入中...' : '确认导入' }}
                </button>
              </div>
            </div>

            <!-- 教师列表容器 -->
            <template v-else>
              <div class="data-table-wrapper" v-if="teacherList.length > 0">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>工号</th>
                      <th>姓名</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="tea in teacherList" :key="tea.id">
                      <td>{{ removePrefix(tea.id) }}</td>
                      <td>{{ tea.username }}</td>
                      <td>
                        <div class="table-actions">
                          <button class="table-action-btn edit" @click="openTeacherModal('edit', tea)">编辑</button>
                          <button class="table-action-btn reset" @click="handleResetTeacherPassword(tea)">重置密码</button>
                          <button class="table-action-btn delete" @click="handleDeleteTeacher(tea)">删除</button>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
                <!-- 传统分页器 -->
                <div class="pagination-bar" v-if="teacherTotalPages > 0">
                  <span class="page-info">共 {{ teacherTotal }} 条，第 {{ teacherPage }}/{{ teacherTotalPages }} 页</span>
                  <button class="page-btn" :disabled="teacherPage <= 1" @click="goToTeacherPage(teacherPage - 1)">
                    <van-icon name="arrow-left" />
                  </button>
                  <button class="page-btn" :disabled="teacherPage >= teacherTotalPages" @click="goToTeacherPage(teacherPage + 1)">
                    <van-icon name="arrow-right" />
                  </button>
                </div>
              </div>
              <div class="scroll-load-indicator" v-if="teacherLoading">加载中...</div>
              <van-empty v-if="!teacherLoading && teacherList.length === 0" description="暂无教师数据" image-size="80" />
            </template>
          </div>
        </template>
        <div v-else class="empty-state">
          <van-empty description="请选择左侧组织进行管理" image-size="120" />
        </div>
      </section>
    </main>

    <!-- ================= 弹窗区 ================= -->
    <!-- 添加/编辑 组织弹窗 -->
    <transition name="modal-fade">
      <div v-if="showOrgModal" class="modal-overlay">
        <div class="modal-card">
          <h3 class="modal-title">{{ orgModalMode === 'add' ? '添加组织' : '编辑组织' }}</h3>
          <div class="modal-field-group">
            <span class="modal-field-label">组织名称</span>
            <input type="text" class="modal-field-input" v-model="orgForm.organization_name" placeholder="请输入组织名称" />
          </div>
          <div class="modal-field-group">
            <span class="modal-field-label">学段</span>
            <select class="modal-field-select" v-model="orgForm.phase">
              <option value="" disabled>请选择学段</option>
              <option value="小学">小学</option>
              <option value="初中">初中</option>
              <option value="高中">高中</option>
              <option value="大学">大学</option>
            </select>
          </div>
          <div class="modal-field-group">
            <span class="modal-field-label">前缀</span>
            <input type="text" class="modal-field-input" v-model="orgForm.prefix" placeholder="请输入登录前缀 (如 gdpu)" />
          </div>
          <div class="modal-actions">
            <button class="modal-btn modal-btn-cancel" @click="showOrgModal = false">取消</button>
            <button class="modal-btn modal-btn-confirm" @click="submitOrgForm">确认</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 添加/编辑 班级弹窗 -->
    <transition name="modal-fade">
      <div v-if="showClassModal" class="modal-overlay">
        <div class="modal-card">
          <h3 class="modal-title">{{ classModalMode === 'add' ? '添加班级' : '编辑班级' }}</h3>
          <div class="modal-field-group">
            <span class="modal-field-label">班级名称</span>
            <input type="text" class="modal-field-input" v-model="classForm.class_name" placeholder="请输入班级名称" />
          </div>
          <div class="modal-actions">
            <button class="modal-btn modal-btn-cancel" @click="showClassModal = false">取消</button>
            <button class="modal-btn modal-btn-confirm" @click="submitClassForm">确认</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 添加/编辑 学生弹窗 -->
    <transition name="modal-fade">
      <div v-if="showStudentModal" class="modal-overlay">
        <div class="modal-card">
          <h3 class="modal-title">{{ studentModalMode === 'add' ? '添加学生' : '编辑学生' }}</h3>
          <div class="modal-field-group">
            <span class="modal-field-label">学号</span>
            <input type="text" class="modal-field-input" v-model="studentForm.id" placeholder="请输入学号" :readonly="studentModalMode === 'edit'" />
          </div>
          <div class="modal-field-group">
            <span class="modal-field-label">姓名</span>
            <input type="text" class="modal-field-input" v-model="studentForm.username" placeholder="请输入姓名" />
          </div>
          <div class="modal-field-group" v-if="studentModalMode === 'edit'">
            <span class="modal-field-label">班级</span>
            <select class="modal-field-select" v-model="studentForm.class_id">
              <option v-for="c in allClassesInOrg" :key="c.class_id" :value="c.class_id">{{ c.class_name }}</option>
            </select>
          </div>
          <div class="modal-field-group" v-if="studentModalMode === 'add'">
            <span class="modal-field-label">班级</span>
            <input type="text" class="modal-field-input" :value="selectedClass?.class_name" readonly />
          </div>
          <div class="modal-field-group">
            <span class="modal-field-label">组织</span>
            <input type="text" class="modal-field-input" :value="selectedOrg.organization_name" readonly />
          </div>
          <div class="modal-actions">
            <button class="modal-btn modal-btn-cancel" @click="showStudentModal = false">取消</button>
            <button class="modal-btn modal-btn-confirm" @click="studentModalMode === 'add' ? submitStudentForm() : submitStudentEdit()">确认</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 添加/编辑 教师弹窗 -->
    <transition name="modal-fade">
      <div v-if="showTeacherModal" class="modal-overlay">
        <div class="modal-card">
          <h3 class="modal-title">{{ teacherModalMode === 'add' ? '添加教师' : '编辑教师' }}</h3>
          <div class="modal-field-group">
            <span class="modal-field-label">工号</span>
            <input type="text" class="modal-field-input" v-model="teacherForm.id" placeholder="请输入工号" :readonly="teacherModalMode === 'edit'" />
          </div>
          <div class="modal-field-group">
            <span class="modal-field-label">姓名</span>
            <input type="text" class="modal-field-input" v-model="teacherForm.username" placeholder="请输入姓名" />
          </div>
          <div class="modal-field-group">
            <span class="modal-field-label">组织</span>
            <input type="text" class="modal-field-input" :value="selectedOrg.organization_name" readonly />
          </div>
          <div class="modal-actions">
            <button class="modal-btn modal-btn-cancel" @click="showTeacherModal = false">取消</button>
            <button class="modal-btn modal-btn-confirm" @click="teacherModalMode === 'add' ? submitTeacherForm() : submitTeacherEdit()">确认</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import * as XLSX from 'xlsx'
import { getOrganizationsPage, createOrganization, updateOrganization, deleteOrganization, getClassesPage, createClass, updateClass, deleteClass, getStudentsPage, createStudent, updateStudent, deleteStudent, getTeachersPage, createTeacher, updateTeacher, deleteTeacher } from "@/api/admin.js"
import AppHeader from '@/components/AppHeader.vue'

const adminName = localStorage.getItem('username') || '管理员'

function debounce(fn, delay) {
  let timer = null
  return (...args) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, args), delay)
  }
}

function formatPrefix(input) {
  return input.replace(/_+$/, '') + '_'
}

function getPurePrefix(prefix) {
  return prefix.replace(/_+$/, '')
}

function getCurrentOrgPrefix() {
  return selectedOrg.value ? formatPrefix(selectedOrg.value.prefix) : ''
}

function removePrefix(id) {
  const prefix = getCurrentOrgPrefix()
  if (prefix && id.startsWith(prefix)) {
    return id.slice(prefix.length)
  }
  return id
}

const getPhaseName = (phase) => {
  const map = {
    primary: "小学",
    junior: "初中",
    senior: "高中",
    university: "大学"
  }
  return map[phase] || phase || "未知"
}

// 组织管理
const orgList = ref([])
const selectedOrg = ref(null)
const orgKeyword = ref('')
const orgLoading = ref(false)

const fetchOrgs = async (isRefresh = true) => {
  orgLoading.value = true
  const res = await getOrganizationsPage({
    page: 1,
    size: 30,
    keyword: orgKeyword.value || null
  }).catch(() => {
  })
  if (res && res.data) {
    orgList.value = res.data.list
  }
  orgLoading.value = false
}

const debouncedOrgSearch = debounce(() => fetchOrgs(true), 300)

const handleOrgSelect = (org) => {
  selectedOrg.value = org
  activeTab.value = 'class'
  classDetailView.value = false
  classKeyword.value = ''
  teacherKeyword.value = ''
  fetchClasses(true)
  fetchTeachers(true)
}

// 组织弹窗
const showOrgModal = ref(false)
const orgModalMode = ref('add')
const orgForm = reactive({
  organization_name: '',
  phase: '',
  prefix: ''
})

const openOrgModal = (mode, org = null) => {
  orgModalMode.value = mode
  if (mode === 'edit' && org) {
    orgForm.organization_name = org.organization_name
    orgForm.phase = getPhaseName(org.phase)
    orgForm.prefix = getPurePrefix(org.prefix)
  } else {
    orgForm.organization_name = ''
    orgForm.phase = ''
    orgForm.prefix = ''
  }
  showOrgModal.value = true
}

const submitOrgForm = async () => {
  if (!orgForm.organization_name.trim() || !orgForm.phase || !orgForm.prefix.trim()) {
    return showToast('请填写完整信息')
  }
  const payload = {
    organization_name: orgForm.organization_name.trim(),
    phase: orgForm.phase,
    prefix: formatPrefix(orgForm.prefix.trim())
  }
  if (orgModalMode.value === 'add') {
    await createOrganization(payload)
    showToast({ message: '创建成功', type: 'success' })
  } else {
    payload.organization_id = selectedOrg.value.organization_id
    await updateOrganization(payload)
    selectedOrg.value = { ...selectedOrg.value, ...payload }
    showToast({ message: '修改成功', type: 'success' })
  }
  showOrgModal.value = false
  fetchOrgs(true)
}

const handleDeleteOrg = async () => {
  const [classRes, teacherRes] = await Promise.all([
    getClassesPage({ organization_id: selectedOrg.value.organization_id, page: 1, size: 1 }).catch(() => ({ data: { total: 0 } })),
    getTeachersPage({ organization_id: selectedOrg.value.organization_id, page: 1, size: 1 }).catch(() => ({ data: { total: 0 } }))
  ])
  const classCount = classRes.data.total
  const teacherCount = teacherRes.data.total
  const msg = `确定删除「${selectedOrg.value.organization_name}」？该操作将同时移除其下 ${classCount} 个班级、${teacherCount} 名教师及所有关联学生，此操作不可恢复。`
  await showConfirmDialog({ title: '删除组织', message: msg }).catch(() => { throw 'cancel' })
  await deleteOrganization({ organization_id: selectedOrg.value.organization_id })
  showToast({ message: '删除成功', type: 'success' })
  selectedOrg.value = null
  fetchOrgs(true)
}

// 班级管理
const activeTab = ref('class')
const classList = ref([])
const classKeyword = ref('')
const classPage = ref(1)
const classHasMore = ref(true)
const classLoading = ref(false)
const classListRef = ref(null)

const fetchClasses = async (isRefresh = false) => {
  if (!selectedOrg.value) return
  if (isRefresh) {
    classList.value = []
    classPage.value = 1
    classHasMore.value = true
  }
  if (classLoading.value || !classHasMore.value) return
  classLoading.value = true
  const res = await getClassesPage({
    organization_id: selectedOrg.value.organization_id,
    page: classPage.value,
    size: 20,
    keyword: classKeyword.value || null
  }).catch(() => {
  })
  if (res && res.data) {
    const { list, total } = res.data
    classList.value.push(...list)
    classHasMore.value = classList.value.length < total
    classPage.value++
  }
  classLoading.value = false
}

const debouncedClassSearch = debounce(() => fetchClasses(true), 300)

const handleClassScroll = () => {
  if (!classListRef.value || classLoading.value || !classHasMore.value) return
  const { scrollTop, scrollHeight, clientHeight } = classListRef.value
  if (scrollTop + clientHeight >= scrollHeight - 50) {
    fetchClasses(false)
  }
}

// 班级弹窗
const showClassModal = ref(false)
const classModalMode = ref('add')
const classForm = reactive({
  class_name: '',
  class_id: null
})

const openClassModal = (mode, cls = null) => {
  classModalMode.value = mode
  if (mode === 'edit' && cls) {
    classForm.class_name = cls.class_name
    classForm.class_id = cls.class_id
  } else {
    classForm.class_name = ''
    classForm.class_id = null
  }
  showClassModal.value = true
}

const submitClassForm = async () => {
  if (!classForm.class_name.trim()) {
    return showToast('班级名称不能为空')
  }
  if (classModalMode.value === 'add') {
    await createClass({
      class_name: classForm.class_name.trim(),
      organization_id: selectedOrg.value.organization_id
    })
    showToast({ message: '添加成功', type: 'success' })
  } else {
    await updateClass({
      class_id: classForm.class_id,
      class_name: classForm.class_name.trim()
    })
    showToast({ message: '修改成功', type: 'success' })
  }
  showClassModal.value = false
  fetchClasses(true)
}

const handleDeleteClassIcon = async (cls) => {
  await showConfirmDialog({
    title: '删除班级',
    message: `确定删除「${cls.class_name}」？此操作不可恢复。`
  }).catch(() => { throw 'cancel' })
  await deleteClass({ class_id: cls.class_id })
  showToast({ message: '删除成功', type: 'success' })
  fetchClasses(true)
}

// 班级详情 & 学生管理
const classDetailView = ref(false)
const selectedClass = ref(null)
const classStudentCount = ref(0)
const allClassesInOrg = ref([])
const classNameEditing = ref('')
const classNameSaving = ref(false)
const classNameError = ref(false)

const handleClassClick = async (cls) => {
  selectedClass.value = cls
  classNameEditing.value = cls.class_name
  classNameError.value = false
  classDetailView.value = true
  importMode.value = false
  const studentRes = await getStudentsPage({
    class_id: cls.class_id,
    page: 1,
    size: 1
  }).catch(() => {
  })
  classStudentCount.value = studentRes.data.total
  const allClassRes = await getClassesPage({
    organization_id: selectedOrg.value.organization_id,
    page: 1,
    size: 999
  }).catch(() => {
  })
  allClassesInOrg.value = allClassRes.data.list
  fetchStudents(true)
}

const handleBackToClasses = () => {
  classDetailView.value = false
  importMode.value = false
}

const handleClassNameBlur = async () => {
  if (classNameEditing.value === selectedClass.value.class_name || classNameSaving.value) return
  if (!classNameEditing.value.trim()) {
    classNameError.value = true
    return
  }
  classNameSaving.value = true
  try {
    await updateClass({
      class_id: selectedClass.value.class_id,
      class_name: classNameEditing.value.trim()
    })
    selectedClass.value.class_name = classNameEditing.value.trim()
    const item = classList.value.find(c => c.class_id === selectedClass.value.class_id)
    if (item) item.class_name = selectedClass.value.class_name
    classNameError.value = false
  } catch (e) {
    classNameError.value = true
  }
  classNameSaving.value = false
}

const handleDeleteClass = async () => {
  await showConfirmDialog({
    title: '删除班级',
    message: `确定删除「${selectedClass.value.class_name}」？该班级下所有学生将一并移除，此操作不可恢复。`
  }).catch(() => { throw 'cancel' })
  await deleteClass({ class_id: selectedClass.value.class_id })
  showToast({ message: '删除成功', type: 'success' })
  handleBackToClasses()
  fetchClasses(true)
}

// 学生列表
const studentList = ref([])
const studentKeyword = ref('')
const studentPage = ref(1)
const studentHasMore = ref(true)
const studentLoading = ref(false)
const studentTableRef = ref(null)

const fetchStudents = async (isRefresh = false) => {
  if (!selectedClass.value) return
  if (isRefresh) {
    studentList.value = []
    studentPage.value = 1
    studentHasMore.value = true
  }
  if (studentLoading.value || !studentHasMore.value) return
  studentLoading.value = true
  const res = await getStudentsPage({
    class_id: selectedClass.value.class_id,
    page: studentPage.value,
    size: 20,
    keyword: studentKeyword.value || null
  }).catch(() => {
  })
  if (res && res.data) {
    const { list, total } = res.data
    studentList.value.push(...list)
    studentHasMore.value = studentList.value.length < total
    studentPage.value++
  }
  studentLoading.value = false
}

const debouncedStudentSearch = debounce(() => fetchStudents(true), 300)

const handleStudentScroll = () => {
  if (!studentTableRef.value || studentLoading.value || !studentHasMore.value) return
  const { scrollTop, scrollHeight, clientHeight } = studentTableRef.value
  if (scrollTop + clientHeight >= scrollHeight - 50) {
    fetchStudents(false)
  }
}

// 学生弹窗
const showStudentModal = ref(false)
const studentModalMode = ref('add')
const studentForm = reactive({
  id: '',
  username: '',
  class_id: null
})

const openStudentModal = (mode, stu = null) => {
  studentModalMode.value = mode
  if (mode === 'edit' && stu) {
    studentForm.id = removePrefix(stu.id)
    studentForm.username = stu.username
    studentForm.class_id = selectedClass.value.class_id
  } else {
    studentForm.id = ''
    studentForm.username = ''
    studentForm.class_id = null
  }
  showStudentModal.value = true
}

const submitStudentForm = async () => {
  if (!studentForm.id.trim() || !studentForm.username.trim()) {
    return showToast('请填写完整信息')
  }
  await createStudent({
    id: getCurrentOrgPrefix() + studentForm.id.trim(),
    username: studentForm.username.trim(),
    password: 'S123456',
    organization_name: selectedOrg.value.organization_name,
    student_class: selectedClass.value.class_name
  })
  showToast({ message: '添加成功', type: 'success' })
  showStudentModal.value = false
  fetchStudents(true)
  classStudentCount.value++
}

const submitStudentEdit = async () => {
  if (!studentForm.username.trim()) return showToast('姓名不能为空')
  const payload = {
    id: getCurrentOrgPrefix() + studentForm.id
  }
  payload.username = studentForm.username.trim()
  if (studentForm.class_id && studentForm.class_id !== selectedClass.value.class_id) {
    payload.class_id = studentForm.class_id
  }
  await updateStudent(payload)
  showToast({ message: '修改成功', type: 'success' })
  showStudentModal.value = false
  fetchStudents(true)
}

const handleResetStudentPassword = async (stu) => {
  await showConfirmDialog({
    title: '重置密码',
    message: `确定将「${stu.username}」的密码重置为默认密码 S123456？`
  }).catch(() => { throw 'cancel' })
  await updateStudent({ id: stu.id, password: 'S123456' })
  showToast({ message: '密码已重置', type: 'success' })
}

const handleDeleteStudent = async (stu) => {
  await showConfirmDialog({
    title: '删除学生',
    message: `确定删除学生「${stu.username}」？此操作不可恢复。`
  }).catch(() => { throw 'cancel' })
  await deleteStudent({ id: stu.id })
  showToast({ message: '删除成功', type: 'success' })
  fetchStudents(true)
  classStudentCount.value--
}

// 学生 Excel 导入
const importMode = ref(false)
const importFile = ref(null)
const importData = ref([])
const importSubmitting = ref(false)

const parseExcel = (file) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    const data = new Uint8Array(e.target.result)
    const workbook = XLSX.read(data, { type: 'array' })
    const sheetName = workbook.SheetNames[0]
    const sheet = workbook.Sheets[sheetName]
    const json = XLSX.utils.sheet_to_json(sheet, { header: 1 })
    const parsed = []
    for (let i = 1; i < json.length; i++) {
      const row = json[i]
      if (!row || row.length === 0) continue
      const id = String(row[0] || '').trim()
      const username = String(row[1] || '').trim()
      const errors = []
      if (!id) errors.push('学号不能为空')
      if (!username) errors.push('姓名不能为空')
      if (id && studentList.value.some(s => String(removePrefix(s.id)) === id)) {
        errors.push('学号在当前列表中已存在')
      }
      parsed.push({
        id,
        username,
        isValid: errors.length === 0,
        errorMsg: errors.join('；')
      })
    }
    importData.value = parsed
  }
  reader.readAsArrayBuffer(file)
}


const handleFileSelect = (e) => {
  const file = e.target.files[0]
  if (!file) return
  importFile.value = file
  parseExcel(file)
}

const handleFileDrop = (e) => {
  e.preventDefault()
  const file = e.dataTransfer.files[0]
  if (!file) return
  importFile.value = file
  parseExcel(file)
}

const handleCancelImport = () => {
  importMode.value = false
  importData.value = []
  importFile.value = null
}

const handleConfirmImport = async () => {
  const validRows = importData.value.filter(r => r.isValid)
  if (validRows.length === 0) {
    return showToast('没有可导入的有效数据')
  }
  importSubmitting.value = true
  const orgPrefix = getCurrentOrgPrefix()
  const results = await Promise.allSettled(
    validRows.map(row => createStudent({
      id: orgPrefix + row.id,
      username: row.username,
      password: 'S123456',
      organization_name: selectedOrg.value.organization_name,
      student_class: selectedClass.value.class_name
    }))
  )
  importSubmitting.value = false
  let successCount = 0
  let failCount = 0
  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      successCount++
    } else {
      failCount++
      const originalRow = importData.value.find(r => r.id === validRows[index].id)
      if (originalRow) {
        originalRow.isValid = false
        originalRow.errorMsg = result.reason?.response?.data?.message || '请求失败'
      }
    }
  })
  showToast({
    message: `成功导入 ${successCount} 条，失败 ${failCount} 条`,
    type: successCount > 0 ? 'success' : 'fail'
  })
  if (failCount === 0) {
    handleCancelImport()
  }
  fetchStudents(true)
  const studentRes = await getStudentsPage({
    class_id: selectedClass.value.class_id,
    page: 1,
    size: 1
  }).catch(() => {
  })
  classStudentCount.value = studentRes.data.total
}

// 教师管理
const teacherList = ref([])
const teacherKeyword = ref('')
const teacherPage = ref(1)
const teacherTotal = ref(0)
const teacherLoading = ref(false)
const teacherTotalPages = computed(() => Math.ceil(teacherTotal.value / 20))

const fetchTeachers = async (isRefresh = false) => {
  if (!selectedOrg.value) return
  if (isRefresh) teacherPage.value = 1
  teacherLoading.value = true
  const res = await getTeachersPage({
    organization_id: selectedOrg.value.organization_id,
    page: teacherPage.value,
    size: 20,
    keyword: teacherKeyword.value || null
  }).catch(() => {
  })
  if (res && res.data) {
    teacherList.value = res.data.list
    teacherTotal.value = res.data.total
  }
  teacherLoading.value = false
}

const debouncedTeacherSearch = debounce(() => fetchTeachers(true), 300)

const goToTeacherPage = (page) => {
  if (page < 1 || page > teacherTotalPages.value) return
  teacherPage.value = page
  fetchTeachers(false)
}

// 教师弹窗
const showTeacherModal = ref(false)
const teacherModalMode = ref('add')
const teacherForm = reactive({
  id: '',
  username: ''
})

const openTeacherModal = (mode, tea = null) => {
  teacherModalMode.value = mode
  if (mode === 'edit' && tea) {
    teacherForm.id = removePrefix(tea.id)
    teacherForm.username = tea.username
  } else {
    teacherForm.id = ''
    teacherForm.username = ''
  }
  showTeacherModal.value = true
}

const submitTeacherForm = async () => {
  if (!teacherForm.id.trim() || !teacherForm.username.trim()) {
    return showToast('请填写完整信息')
  }
  await createTeacher({
    id: getCurrentOrgPrefix() + teacherForm.id.trim(),
    username: teacherForm.username.trim(),
    password: 'T123456',
    organization_name: selectedOrg.value.organization_name
  })
  showToast({ message: '添加成功', type: 'success' })
  showTeacherModal.value = false
  fetchTeachers(true)
}

const submitTeacherEdit = async () => {
  if (!teacherForm.username.trim()) return showToast('姓名不能为空')
  await updateTeacher({
    id: getCurrentOrgPrefix() + teacherForm.id,
    username: teacherForm.username.trim()
  })
  showToast({ message: '修改成功', type: 'success' })
  showTeacherModal.value = false
  fetchTeachers(false)
}

const handleResetTeacherPassword = async (tea) => {
  await showConfirmDialog({
    title: '重置密码',
    message: `确定将「${tea.username}」的密码重置为默认密码 T123456？`
  }).catch(() => { throw 'cancel' })
  await updateTeacher({ id: tea.id, password: 'T123456' })
  showToast({ message: '密码已重置', type: 'success' })
}

const handleDeleteTeacher = async (tea) => {
  await showConfirmDialog({
    title: '删除教师',
    message: `确定删除教师「${tea.username}」？此操作不可恢复。`
  }).catch(() => { throw 'cancel' })
  await deleteTeacher({ id: tea.id })
  showToast({ message: '删除成功', type: 'success' })
  fetchTeachers(false)
}

// 教师 Excel 批量导入
const teacherImportMode = ref(false)
const teacherImportFile = ref(null)
const teacherImportData = ref([])
const teacherImportSubmitting = ref(false)

/**
 * 解析教师 Excel 文件并执行前端校验
 * @param {File} file - 用户上传的 Excel 文件对象
 */
/**
 * 解析教师 Excel 文件并执行前端校验
 * @param {File} file - 用户上传的 Excel 文件对象
 */
const parseTeacherExcel = (file) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    const data = new Uint8Array(e.target.result)
    const workbook = XLSX.read(data, { type: 'array' })
    const sheetName = workbook.SheetNames[0]
    const sheet = workbook.Sheets[sheetName]
    const json = XLSX.utils.sheet_to_json(sheet, { header: 1 })
    const parsed = []
    for (let i = 1; i < json.length; i++) {
      const row = json[i]
      if (!row || row.length === 0) continue
      const id = String(row[0] || '').trim()
      const username = String(row[1] || '').trim()
      const errors = []
      if (!id) errors.push('工号不能为空')
      if (!username) errors.push('姓名不能为空')
      if (id && teacherList.value.some(s => String(removePrefix(s.id)) === id)) {
        errors.push('工号在当前列表中已存在')
      }
      parsed.push({
        id,
        username,
        isValid: errors.length === 0,
        errorMsg: errors.join('；')
      })
    }
    teacherImportData.value = parsed
  }
  reader.readAsArrayBuffer(file)
}


const handleTeacherFileSelect = (e) => {
  const file = e.target.files[0]
  if (!file) return
  teacherImportFile.value = file
  parseTeacherExcel(file)
}

const handleTeacherFileDrop = (e) => {
  e.preventDefault()
  const file = e.dataTransfer.files[0]
  if (!file) return
  teacherImportFile.value = file
  parseTeacherExcel(file)
}

const handleCancelTeacherImport = () => {
  teacherImportMode.value = false
  teacherImportData.value = []
  teacherImportFile.value = null
}

/**
 * 确认导入教师数据
 * 调用创建教师接口，默认密码 T123456
 */
const handleConfirmTeacherImport = async () => {
  const validRows = teacherImportData.value.filter(r => r.isValid)
  if (validRows.length === 0) {
    return showToast('没有可导入的有效数据')
  }
  teacherImportSubmitting.value = true
  const orgPrefix = getCurrentOrgPrefix()
  const results = await Promise.allSettled(
    validRows.map(row => createTeacher({
      id: orgPrefix + row.id,
      username: row.username,
      password: 'T123456',
      organization_name: selectedOrg.value.organization_name
    }))
  )
  teacherImportSubmitting.value = false
  let successCount = 0
  let failCount = 0
  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      successCount++
    } else {
      failCount++
      const originalRow = teacherImportData.value.find(r => r.id === validRows[index].id)
      if (originalRow) {
        originalRow.isValid = false
        originalRow.errorMsg = result.reason?.response?.data?.message || '请求失败'
      }
    }
  })
  showToast({
    message: `成功导入 ${successCount} 条，失败 ${failCount} 条`,
    type: successCount > 0 ? 'success' : 'fail'
  })
  if (failCount === 0) {
    handleCancelTeacherImport()
  }
  fetchTeachers(true)
}

onMounted(() => {
  fetchOrgs(true)
})
</script>

<style scoped src="../../styles/views/admin/AdminManagement.css"></style>
