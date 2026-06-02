<template>
  <div class="course-teacher-page page-fade-enter">
    <AppHeader role="teacher" :userName="teacherName"/>
    <div class="main-body">
      <!-- 左侧：导航与信息区 -->
      <aside class="left-panel">
        <div class="left-panel-inner">
          <div class="course-info-card">
            <img :src="courseInfo.cover" alt="课程封面" class="course-cover"/>
            <h2 class="course-name">{{ courseInfo.name }}</h2>
            <p class="course-teacher">{{ courseInfo.teacher }}</p>
            <button v-if="isEditMode" class="delete-course-btn" @click="handleDeleteCourse">删除课程</button>
          </div>
          <div class="view-switcher-col" v-if="!isEditMode">
            <div class="switch-tab-row" :class="{ active: activeLeftTab === 'chapter' }"
                 @click="activeLeftTab = 'chapter'">
              <span>章节</span>
              <div class="active-indicator" v-if="activeLeftTab === 'chapter'"></div>
            </div>
            <div class="switch-tab-row" :class="{ active: activeLeftTab === 'task' }" @click="activeLeftTab = 'task'">
              <span>任务</span>
              <div class="active-indicator" v-if="activeLeftTab === 'task'"></div>
            </div>
            <div class="switch-tab-row" :class="{ active: activeLeftTab === 'gai-task' }"
                 @click="activeLeftTab = 'gai-task'">
              <span>人机交互任务</span>
              <div class="active-indicator" v-if="activeLeftTab === 'gai-task'"></div>
            </div>
            <div v-if="!isEditMode" class="switch-tab-row" :class="{ active: activeLeftTab === 'analysis' }"
                 @click="switchToAnalysis">
              <span>学生学习分析</span>
              <div class="active-indicator" v-if="activeLeftTab === 'analysis'"></div>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右侧：内容区 -->
      <main class="right-panel">
        <div class="right-top-content blur-vertical" ref="rightTopContentRef">
          <!-- 视图一：章节 -->
          <div v-if="activeLeftTab === 'chapter'" class="chapter-view">
            <div v-if="chapterList.length === 0 && isEditMode" class="empty-chapter-add" @click="insertChapter(0)">
              <van-icon name="plus" size="24" color="#4A90E2"/>
            </div>
            <template v-else>
              <div v-for="(chapter, cIndex) in chapterList" :key="chapter.id" class="chapter-wrapper">
                <div v-if="isEditMode" class="insert-bar" @click="insertChapter(cIndex)">
                  <van-icon name="plus" size="14" color="#4A90E2"/>
                </div>
                <div class="chapter-group">
                  <div class="chapter-header" @click.self="toggleChapter(cIndex)">
                    <div class="header-left">
                      <span v-if="!isEditMode || editingChapterId !== chapter.id" class="chapter-title"
                            @click="handleChapterClick(chapter)">{{ chapter.title }}</span>
                      <input v-else type="text" class="chapter-title-input" v-model="chapter.title" v-focus
                             @blur="editingChapterId = null" @keyup.enter="editingChapterId = null"/>
                    </div>
                    <div class="header-right">
                      <div v-if="isEditMode" class="action-btn-circle btn-danger" @click.stop="deleteChapter(cIndex)">
                        <van-icon name="minus" size="14"/>
                      </div>
                      <van-icon name="arrow" class="arrow-icon" :class="{ 'is-expanded': chapter.expanded }"
                                @click="toggleChapter(cIndex)"/>
                    </div>
                  </div>
                  <div class="section-list" :class="{ 'is-expanded': chapter.expanded }">
                    <div v-for="(section, sIndex) in chapter.sections" :key="section.id" class="section-item"
                         @click="handleSectionClick(section, chapter)">
                      <div class="section-item-left">
                        <div class="status-icon" :class="section.hasResource ? 'status-done' : 'status-pending'">
                          <van-icon v-if="section.hasResource" name="success" color="#FFFFFF" size="12"/>
                          <span v-else>{{ sIndex + 1 }}</span>
                        </div>
                        <span class="section-name">{{ section.title }}</span>
                      </div>
                      <div v-if="isEditMode" class="section-item-right" @click.stop>
                        <div class="action-btn-circle btn-danger" @click.stop="deleteSection(cIndex, sIndex)">
                          <van-icon name="minus" size="14"/>
                        </div>
                      </div>
                    </div>
                    <div v-if="isEditMode" class="add-section-btn"
                         @click.stop="openSectionModal(chapter.localId || chapter.id)">
                      <van-icon name="plus" size="16" color="#4A90E2"/>
                      <span>添加小节</span>
                    </div>
                  </div>
                </div>
                <div v-if="isEditMode && cIndex === chapterList.length - 1" class="insert-bar"
                     @click="insertChapter(cIndex + 1)">
                  <van-icon name="plus" size="14" color="#4A90E2"/>
                </div>
              </div>
            </template>
          </div>

          <!-- 视图二：任务 -->
          <div v-if="activeLeftTab === 'task'" class="task-view">
            <div v-for="(t, index) in taskList" :key="t.task_id" class="task-card" @click="handleTaskClick(t)">
              <div class="task-col-left">
                <van-icon :name="t.type === 'homework' ? 'edit' : 'orders-o'" class="task-type-icon"/>
              </div>
              <div class="task-col-middle"><span class="task-name">{{ t.task_title }}</span></div>
              <div class="task-col-right">
                <span v-if="!isEditMode && t.deadline" class="countdown-text"
                      :class="{ 'is-expired': getCountdown(t.deadline) === '已截止' }">{{
                    getCountdown(t.deadline)
                  }}</span>
                <div v-if="isEditMode" class="action-btn-circle btn-danger" @click.stop="deleteTask(index, 'task')">
                  <van-icon name="minus" size="14"/>
                </div>
              </div>
            </div>
            <div v-if="isEditMode" class="empty-chapter-add mt-16" @click="openTaskModal(null)">
              <van-icon name="plus" size="24" color="#4A90E2"/>
            </div>
          </div>

          <!-- 视图三：人机交互任务 -->
          <div v-if="activeLeftTab === 'gai-task'" class="task-view">
            <div v-for="(gt, index) in gaiTaskList" :key="gt.analysis_task_id" class="task-card"
                 @click="handleGaiTaskClick(gt)">
              <div class="task-col-left">
                <van-icon name="chat-o" class="task-type-icon"/>
              </div>
              <div class="task-col-middle"><span class="task-name">{{ gt.analysis_task_title }}</span></div>
              <div class="task-col-right">
                <span v-if="!isEditMode && gt.deadline" class="countdown-text"
                      :class="{ 'is-expired': getCountdown(gt.deadline) === '已截止' }">{{
                    getCountdown(gt.deadline)
                  }}</span>
                <div v-if="isEditMode" class="action-btn-circle btn-danger" @click.stop="deleteTask(index, 'gai-task')">
                  <van-icon name="minus" size="14"/>
                </div>
              </div>
            </div>
            <div v-if="isEditMode" class="empty-chapter-add mt-16" @click="openGaiTaskModal(null)">
              <van-icon name="plus" size="24" color="#4A90E2"/>
            </div>
          </div>

          <!-- 视图四：学生学习分析 -->
          <div v-if="activeLeftTab === 'analysis'" class="analysis-view-container">
            <div class="analysis-left-list blur-vertical">
              <div class="analysis-stu-item" :class="{ active: selectedAnalysisStudentId === 'all' }"
                   @click="selectAnalysisStudent('all')">
                全部
              </div>
              <template v-for="group in groupStudentsByClass(studentList)" :key="group.class_name">
                <div class="class-group-card">
                  <div class="class-group-header" @click="toggleClassExpand('analysis-', group.class_name)">
                    <span class="class-group-title">{{ group.class_name }}</span>
                    <van-icon name="arrow" class="class-arrow"
                              :class="{ 'is-expanded': isClassExpanded('analysis-', group.class_name) }"/>
                  </div>
                  <transition name="class-slide">
                    <div class="class-group-body-inner" v-if="isClassExpanded('analysis-', group.class_name)">
                      <div v-for="stu in group.students" :key="stu.id" class="analysis-stu-item"
                           :class="{ active: selectedAnalysisStudentId === stu.id }"
                           @click="selectAnalysisStudent(stu.id)">
                        {{ stu.name }}
                      </div>
                    </div>
                  </transition>
                </div>
              </template>
            </div>
            <div class="analysis-right-content">
              <div v-if="analysisLoading" style="display: flex; justify-content: center; padding: 60px 0;">
                <van-loading size="36px" vertical color="#1989fa">正在分析数据...</van-loading>
              </div>
              <template v-else>
                <div class="analysis-charts-row">
                  <div class="analysis-chart-box">
                    <van-circle v-model:current-rate="currentAnalysisChapterRate" :rate="analysisRates.chapterRate"
                                :speed="100" color="#4A90E2" size="80px" :stroke-width="10">
                      <div class="circle-inner"><span class="circle-text-sm">{{ analysisData.chapterDone }}%</span>
                      </div>
                    </van-circle>
                    <span class="analysis-chart-label">章节</span>
                  </div>
                  <div class="analysis-chart-box">
                    <van-circle v-model:current-rate="currentAnalysisTaskRate" :rate="analysisRates.taskRate"
                                :speed="100" color="#10B981" size="80px" :stroke-width="10">
                      <div class="circle-inner"><span class="circle-text-sm">{{ analysisData.taskDone }}%</span></div>
                    </van-circle>
                    <span class="analysis-chart-label">任务</span>
                    <span class="analysis-chart-score">完成质量：{{ analysisData.taskQuality }}</span>
                  </div>
                  <div class="analysis-chart-box">
                    <van-circle v-model:current-rate="currentAnalysisGaiRate" :rate="analysisRates.gaiRate" :speed="100"
                                color="#8B5CF6" size="80px" :stroke-width="10">
                      <div class="circle-inner"><span class="circle-text-sm">{{ analysisData.gaiDone }}%</span></div>
                    </van-circle>
                    <span class="analysis-chart-label">人机交互任务</span>
                  </div>
                </div>
                <div class="analysis-text-area blur-vertical">
                  <div class="analysis-text markdown-body" v-html="renderedAnalysisText"></div>
                  <div class="ai-disclaimer-tip">
                    {{ isStreaming ? 'AI正在生成...' : '内容由AI生成，请仔细甄别' }}
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- === 右侧下区域：编辑控制栏 === -->
        <div class="right-bottom-bar" v-show="activeLeftTab !== 'analysis'">
          <div class="bottom-left">
            <div class="invite-btn-glow" :class="isInvitationValid ? 'glow-valid' : 'glow-invalid'">
              <button class="invite-code-btn" @click="openInviteModal">
                <van-icon name="description"/>
                邀请码
              </button>
            </div>
          </div>
          <div class="bottom-right">
            <button class="toggle-edit-btn" :class="{ 'is-editing': isEditMode }" @click="toggleEditMode"
                    :disabled="isSaving">
              {{ isSaving ? '保存中...' : (isEditMode ? '完成编辑' : '编辑') }}
            </button>
          </div>
        </div>
      </main>
    </div>

    <!-- ================= 全局模态遮罩集合 ================= -->
    <teleport to="body">
  <transition name="fade">
    <div v-if="showDetailPanel" class="global-agi-overlay" @click="handleGlobalOverlayClick"></div>
  </transition>
      <!-- 1. 预览模式：详情面板 -->
      <div v-if="showDetailPanel && !isEditMode">
        <div class="detail-paired-panel">
          <div class="detail-panel-header">
            <h3>{{ detailTargetName }}</h3>
            <div class="close-detail-btn" @click="closeDetailPanel">
              <van-icon name="cross" size="20"/>
            </div>
          </div>
          <div class="detail-charts-row">
            <div class="chart-box">
              <van-circle v-model:current-rate="currentCompRate" :rate="detailData.completionRate" :speed="100"
                          color="#4A90E2" size="90px" :stroke-width="15">
                <div class="circle-inner"><span class="circle-text">{{ currentCompRate.toFixed(0) }}%</span></div>
              </van-circle>
              <span class="chart-label">{{
                  detailType === 'section' ? '学习人数/全部人数' : '完成人数/全部人数'
                }}</span>
            </div>
            <div class="chart-box">
              <van-circle v-model:current-rate="currentScoreRate" :rate="detailData.scoreRate" :speed="100"
                          color="#10B981" size="90px" :stroke-width="15">
                <div class="circle-inner"><span class="circle-text">{{
                    detailType === 'section' ? (currentScoreRate / 20).toFixed(1) : currentScoreRate.toFixed(0)
                  }}</span></div>
              </van-circle>
              <span class="chart-label">{{ detailType === 'section' ? '实际学习效果/5分' : '平均得分/100分' }}</span>
            </div>
          </div>
          <div class="detail-lists-row">
            <div class="list-col left-list blur-vertical">
              <h4>{{ detailType === 'section' ? '已学习学生' : '已完成学生' }}</h4>
              <template v-for="group in groupStudentsByClass(detailData.completedStudents, 'name')"
                        :key="group.class_name">
                <div class="class-group-card">
                  <div class="class-group-header" @click="toggleClassExpand('completed-', group.class_name)">
                    <span class="class-group-title">{{ group.class_name }}</span>
                    <van-icon name="arrow" class="class-arrow"
                              :class="{ 'is-expanded': isClassExpanded('completed-', group.class_name) }"/>
                  </div>
                  <transition name="class-slide">
                    <div class="class-group-body-inner" v-if="isClassExpanded('completed-', group.class_name)">
                      <div class="list-row" v-for="(stu, idx) in group.students" :key="idx">
                        <span class="stu-name">{{ stu.name }}</span>
                        <span class="stu-score">{{ detailType === 'section' ? '学习质量：' : '任务得分：' }}{{
                            stu.score
                          }}</span>
                      </div>
                    </div>
                  </transition>
                </div>
              </template>
            </div>
            <div class="list-col right-list blur-vertical">
              <h4>{{ detailType === 'section' ? '未学习学生' : '未完成学生' }}</h4>
              <template v-for="group in groupStudentsByClass(detailData.uncompletedStudents, 'name')"
                        :key="group.class_name">
                <div class="class-group-card">
                  <div class="class-group-header" @click="toggleClassExpand('uncompleted-', group.class_name)">
                    <span class="class-group-title">{{ group.class_name }}</span>
                    <van-icon name="arrow" class="class-arrow"
                              :class="{ 'is-expanded': isClassExpanded('uncompleted-', group.class_name) }"/>
                  </div>
                  <transition name="class-slide">
                    <div class="class-group-body-inner" v-if="isClassExpanded('uncompleted-', group.class_name)">
                      <div class="list-row" v-for="(stu, idx) in group.students" :key="idx">
                        <span class="stu-name">{{ stu.name }}</span>
                        <span class="stu-score empty">-</span>
                      </div>
                    </div>
                  </transition>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- 2. 人机交互任务预览 -->
      <transition name="fade">
        <div v-if="showGaiTaskDetailPanel && !isEditMode" class="modal-overlay glass-overlay"
             @click.self="showGaiTaskDetailPanel = false">
          <div class="gai-detail-panel">
            <div class="gai-detail-header">
              <h3>人机交互任务：{{ currentGaiTask?.analysis_task_title }}</h3>
              <div class="close-detail-btn" @click="showGaiTaskDetailPanel = false">
                <van-icon name="cross" size="24"/>
              </div>
            </div>
            <div class="gai-detail-body">
              <div class="gai-col-stu blur-vertical">
                <template v-for="group in groupStudentsByClass(gaiTaskStudentList)" :key="group.class_name">
                  <div class="class-group-card">
                    <div class="class-group-header" @click="toggleClassExpand('gai-', group.class_name)">
                      <span class="class-group-title">{{ group.class_name }}</span>
                      <van-icon name="arrow" class="class-arrow"
                                :class="{ 'is-expanded': isClassExpanded('gai-', group.class_name) }"/>
                    </div>
                    <transition name="class-slide">
                      <div class="class-group-body-inner" v-if="isClassExpanded('gai-', group.class_name)">
                        <div v-for="stu in group.students" :key="stu.id" class="analysis-stu-item"
                             :class="{ active: selectedGaiStudentId === stu.id,'student-not-completed': !stu.is_completed }"
                             @click="selectGaiStudent(stu.id)">
                          {{ stu.name }}
                        </div>
                      </div>
                    </transition>
                  </div>
                </template>
              </div>
              <div class="gai-col-analysis blur-vertical">
                <h4>综合对话分析</h4>
                <div class="markdown-body" v-html="renderedGaiAnalysisText"></div>
                <div class="ai-disclaimer-tip">
                  {{ isGaiStreaming ? 'AI正在生成...' : '内容由AI生成，请仔细甄别' }}
                </div>
              </div>
              <div class="gai-col-chat blur-vertical">
                <h4>对话记录留存</h4>
                <div v-for="msg in currentGaiTask?.chatHistory" :key="msg.id"
                     :class="['message-wrapper', msg.role === 'assistant' ? 'left' : 'right']">
                  <div class="message-bubble" v-html="renderMd(msg.content)"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </transition>
      <!-- 3. 人机交互任务编辑弹窗 -->
      <transition name="modal-fade">
        <div v-if="showGaiTaskModal" class="modal-overlay" @click.self="closeGaiTaskModal">
          <div class="gai-task-modal-content">
            <!-- 头部：标题 + 截止时间 -->
            <div class="gai-task-modal-header">
              <h3>{{ currentGaiTask ? '编辑人机交互任务' : '发布人机交互任务' }}</h3>
              <div class="deadline-trigger" @click="showGaiTimePicker = true">
                <van-icon name="clock-o" size="16"/>
                <span>{{
                    gaiTaskForm.deadline ? formatDisplayTime(gaiTaskForm.deadline) : '设置截止时间 (必填)'
                  }}</span>
              </div>
            </div>

            <!-- 内容滚动区 -->
            <div class="gai-task-modal-body">
              <div class="gai-form-item">
                <label class="gai-form-item-label">标题</label>
                <input type="text" class="custom-input" v-model="gaiTaskForm.title" placeholder="请输入标题"/>
              </div>

              <div class="gai-form-item gai-flex-item">
                <label class="gai-form-item-label">任务描述</label>
                <textarea class="custom-textarea" v-model="gaiTaskForm.desc"
                          placeholder="课程学生可见，指导学生如何与AI交互"></textarea>
              </div>

              <div class="gai-form-item gai-flex-item">
                <label class="gai-form-item-label">分析需求</label>
                <textarea class="custom-textarea" v-model="gaiTaskForm.analysisReq"
                          placeholder="告诉后台系统如何分析学生的对话记录"></textarea>
              </div>

              <div class="gai-form-item">
                <label class="gai-form-item-label">评分</label>
                <textarea class="custom-textarea" v-model="gaiTaskForm.scoreRule"
                          placeholder="如：探索深度40%，逻辑性60%"></textarea>
              </div>
            </div>

            <!-- 底部操作栏 -->
            <div class="gai-task-modal-footer">
              <button class="modal-btn btn-cancel" @click="closeGaiTaskModal">取消</button>
              <button class="modal-btn btn-submit" @click="saveGaiTask">提交</button>
            </div>

            <!-- 时间选择器弹窗 -->
            <van-popup v-model:show="showGaiTimePicker" class="center-time-popup" position="center" :overlay="false"
                       teleport="body" :z-index="3001">
              <div class="time-picker-wrapper" @wheel.prevent="handleTimePickerWheel">
                <div class="time-picker-header">
                  <span @click="clearGaiTime" class="tp-btn clear">清除</span>
                  <span class="tp-title">选择截止时间</span>
                  <span @click="confirmGaiTime" class="tp-btn confirm">确定</span>
                </div>
                <van-date-picker v-model="gaiTimePickerValue" :show-toolbar="false"/>
              </div>
            </van-popup>
          </div>
        </div>
      </transition>


      <!-- 4. 小节编辑/查看表单 -->
      <transition name="modal-fade">
        <div v-if="showSectionModal" class="modal-overlay" @click.self="showSectionModal = false">
          <div class="subtask-modal-content">
            <h3>{{ isSectionModalReadOnly ? '查看小节' : (currentSection ? '编辑小节' : '添加小节') }}</h3>
            <input type="text" class="custom-input" :class="{'is-readonly': isSectionModalReadOnly}"
                   v-model="sectionForm.title" placeholder="请输入小节名称" :readonly="isSectionModalReadOnly"/>
            <div class="type-selector" :class="{'is-readonly': isSectionModalReadOnly}">
              <div class="type-btn" :class="{ active: sectionForm.type === 'video' }"
                   @click="!isSectionModalReadOnly && (sectionForm.type = 'video')">视频
              </div>
              <div class="type-btn" :class="{ active: sectionForm.type === 'pdf' }"
                   @click="!isSectionModalReadOnly && (sectionForm.type = 'pdf')"> PDF
              </div>
            </div>
            <div class="upload-area"
                 :class="[isSectionModalReadOnly ? 'is-readonly' : '', sectionFileError ? 'has-error' : '']"
                 @click="simulateUpload">
              <van-icon :name="sectionForm.fileUploaded ? 'success' : 'cloud-o'" size="24"
                        :color="sectionForm.fileUploaded ? '#10B981' : '#4A90E2'"/>
              <span>{{
                  sectionForm.fileUploaded ? '资料已就绪' : `点击上传 ${sectionForm.type === 'video' ? '视频' : 'PDF'} 资料`
                }}</span>
            </div>
            <input ref="fileInputRef" type="file" style="display: none;"
                   :accept="sectionForm.type === 'video' ? 'video/*' : '.pdf'" @change="handleFileChange"/>
            <div class="error-msg" v-if="sectionFileError && !isSectionModalReadOnly">必须上传对应资料才可保存</div>
            <textarea class="custom-textarea" :class="{'is-readonly': isSectionModalReadOnly}"
                      v-model="sectionForm.description" placeholder="请输入学习内容介绍（选填）"
                      :readonly="isSectionModalReadOnly"></textarea>
            <div class="modal-footer" v-if="!isSectionModalReadOnly">
              <button class="modal-btn btn-cancel" @click="showSectionModal = false">取消</button>
              <button class="modal-btn btn-submit" @click="saveSection">保存</button>
            </div>
          </div>
        </div>
      </transition>

      <!-- 5. 任务组卷编辑器 -->
      <transition name="modal-fade">
        <div v-if="showTaskModal" class="modal-overlay" @click.self="closeTaskModal">
          <div class="task-modal-content">
            <div class="task-modal-header">
              <h3 style="white-space: nowrap;">{{ currentTask ? '编辑任务' : '创建任务' }}</h3>
              <input type="text" class="custom-input title-input flex-1" v-model="taskForm.title"
                     placeholder="请输入任务名称" style="margin: 0 16px;"/>
              <div class="deadline-trigger" @click="showTaskTimePicker = true">
                <van-icon name="clock-o" size="16"/>
                <span>{{ taskForm.deadline ? formatDisplayTime(taskForm.deadline) : '设置截止时间' }}</span>
              </div>
            </div>
            <van-popup v-model:show="showTaskTimePicker" class="center-time-popup" position="center" :overlay="false"
                       teleport="body" :z-index="3001">
              <div class="time-picker-wrapper" @wheel.prevent="handleTimePickerWheel">
                <div class="time-picker-header">
                  <span @click="clearTaskTime" class="tp-btn clear">清除</span>
                  <span class="tp-title">选择截止时间</span>
                  <span @click="confirmTaskTime" class="tp-btn confirm">确定</span>
                </div>
                <van-date-picker v-model="taskTimePickerValue" :show-toolbar="false"/>
              </div>
            </van-popup>
            <div class="task-modal-body blur-vertical">
              <div v-if="isTaskDetailLoading"
                   style="display: flex; justify-content: center; align-items: center; min-height: 200px;">
                <van-loading size="36px" vertical color="#1989fa">正在获取题目...</van-loading>
              </div>
              <template v-else>
                <div v-for="(q, qIndex) in taskForm.questions" :key="q.id" class="question-edit-card"
                     :id="'question-card-' + qIndex"
                     :class="{ 'has-validation-error': q.hasError, 'shake-animation': q.isShaking }">
                  <div v-if="taskForm.questions.length > 1" class="action-btn-circle btn-danger q-delete-btn"
                       @click="taskForm.questions.splice(qIndex, 1)">
                    <van-icon name="minus" size="14"/>
                  </div>
                  <div class="q-card-inner">
                    <div class="q-type-sidebar">
                      <div class="q-type-btn" :class="{ active: q.type === 'single' }" @click="q.type = 'single'">单选
                      </div>
                      <div class="q-type-btn" :class="{ active: q.type === 'multiple' }" @click="q.type = 'multiple'">
                        多选
                      </div>
                      <div class="q-type-btn" :class="{ active: q.type === 'judge' }" @click="q.type = 'judge'">判断
                      </div>
                      <div class="q-type-btn" :class="{ active: q.type === 'subjective' }"
                           @click="q.type = 'subjective'">主观
                      </div>
                    </div>
                    <div class="q-content-editor">
                      <textarea class="custom-textarea q-title-input" v-model="q.title"
                                placeholder="请输入题目内容"></textarea>
                      <div v-if="q.type === 'single'" class="options-edit-list">
                        <div v-for="(opt, optIndex) in q.options" :key="opt.id" class="option-edit-row">
                          <div class="mock-radio" :class="{ 'is-correct': q.correctAnswerId === opt.id }"
                               @click="q.correctAnswerId = opt.id">
                            <van-icon v-if="q.correctAnswerId === opt.id" name="success" size="12"/>
                          </div>
                          <input type="text" class="custom-input opt-input" v-model="opt.content"
                                 :placeholder="`选项 ${String.fromCharCode(65 + optIndex)} 内容`"/>
                        </div>
                      </div>
                      <div v-else-if="q.type === 'multiple'" class="options-edit-list">
                        <div v-for="(opt, optIndex) in q.options" :key="opt.id" class="option-edit-row">
                          <div class="mock-checkbox" :class="{ 'is-correct': q.correctAnswerIds.includes(opt.id) }"
                               @click="toggleCorrectAnswer(q, opt.id)">
                            <van-icon v-if="q.correctAnswerIds.includes(opt.id)" name="success" size="12"/>
                          </div>
                          <input type="text" class="custom-input opt-input" v-model="opt.content"
                                 :placeholder="`选项 ${String.fromCharCode(65 + optIndex)} 内容`"/>
                        </div>
                      </div>
                      <div v-else-if="q.type === 'judge'" class="judge-edit-row">
                        <div class="judge-mock-btn" :class="{ 'is-correct': q.correctAnswerId === 'true' }"
                             @click="q.correctAnswerId = 'true'">
                          <div class="mock-radio" :class="{ 'is-correct': q.correctAnswerId === 'true' }">
                            <van-icon v-if="q.correctAnswerId === 'true'" name="success" size="12"/>
                          </div>
                          正确
                        </div>
                        <div class="judge-mock-btn" :class="{ 'is-correct': q.correctAnswerId === 'false' }"
                             @click="q.correctAnswerId = 'false'">
                          <div class="mock-radio" :class="{ 'is-correct': q.correctAnswerId === 'false' }">
                            <van-icon v-if="q.correctAnswerId === 'false'" name="success" size="12"/>
                          </div>
                          错误
                        </div>
                      </div>
                      <div v-else-if="q.type === 'subjective'" class="subjective-edit-area">
                        <textarea class="custom-textarea refer-answer-input" v-model="q.referAnswer"
                                  placeholder="请输入参考答案（选填）"></textarea>
                      </div>
                    </div>
                  </div>
                  <div class="action-btn-circle btn-primary q-add-btn" @click="addQuestion(qIndex)">
                    <van-icon name="plus" size="14"/>
                  </div>
                </div>
              </template>
            </div>
            <div class="task-modal-footer">
              <button class="modal-btn btn-cancel" @click="closeTaskModal">取消</button>
              <button class="modal-btn btn-submit" @click="saveTask">提交</button>
            </div>
          </div>
        </div>
      </transition>

      <!-- 6. 邀请码弹窗 -->
      <transition name="modal-fade">
        <div v-if="showInviteModal" class="modal-overlay" @click.self="showInviteModal = false">
          <div class="invite-modal-content">
            <div class="invite-modal-header">
              <h2 class="invite-title">邀请码</h2>
              <van-icon name="cross" size="20" color="#999" class="invite-close-btn" @click="showInviteModal = false"/>
            </div>
            <div class="invite-code-display">{{ inviteCode }}</div>
            <div class="invite-switch-section">
              <div class="invite-switch" :class="isInvitationValid ? 'switch-valid' : 'switch-invalid'"
                   @click="toggleInvitationValid">
                <div class="switch-slider" :class="{ 'slide-right': !isInvitationValid }">
                  <span v-if="isInvitationValid" class="slider-text text-green">有效</span>
                  <span v-else class="slider-text text-red">无效</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </transition>
    </teleport>

    <GAI
        ref="agiRef"
        :hideTrigger="showDetailPanel"
        class="course-teacher-gai"
        :class="{'is-paired-mode': showDetailPanel}"
        roleSuffix="teacher"
        :overlay="!showDetailPanel"
    />
  </div>
</template>

<style scoped src="../../styles/views/teacher/CourseTeacher.css"></style>


<script setup>
import {onMounted, onUnmounted, reactive, ref, nextTick} from 'vue'
import {useRoute, useRouter} from 'vue-router'
import {showConfirmDialog, showToast} from 'vant'
import AppHeader from '@/components/AppHeader.vue'
import GAI from '@/components/GAI.vue'
import MarkdownIt from 'markdown-it'
import texmath from 'markdown-it-texmath'
import katex from 'katex'
import DOMPurify from 'dompurify'
import {
  create_gai_task,
  create_task,
  delete_course,
  delete_gai_task,
  delete_task,
  get_analysis_ai_text_for_student_study,
  get_analysis_raw_records,
  get_chapters,
  get_completion_details,
  get_course_detail,
  get_course_students,
  get_gai_student_analysis,
  get_gai_task_students,
  get_gai_tasks,
  get_tasks,
  update_chapters_batch,
  update_course,
  update_gai_task,
  update_task,
  upload_resource,
  get_task_detail_for_edit
} from '@/api/course.js'

const md = new MarkdownIt({html: false, breaks: true}).use(texmath, {engine: katex, delimiters: 'dollars'})

const renderMd = (raw) => DOMPurify.sanitize(md.render(raw), {USE_PROFILES: {html: true, mathMl: true}})

const router = useRouter()
const route = useRoute()
const agiRef = ref(null)
const vFocus = {mounted: (el) => el.focus()}

const isEditMode = ref(false)
const isSaving = ref(false)
const activeLeftTab = ref('chapter')
const teacherName = ref(localStorage.getItem('username'))
const analysisLoading = ref(false)
const showInviteModal = ref(false)
const isInvitationValid = ref(false)
const inviteCode = ref('')

const toggleInvitationValid = async () => {
  const newState = !isInvitationValid.value
  await update_course(courseInfo.id, {is_invitation_valid: newState})
  isInvitationValid.value = newState
  showToast({message: newState ? '邀请码已开启' : '邀请码已关闭', type: 'success'})
}
const handleGlobalOverlayClick = () => {
  if (showDetailPanel.value) {
    closeDetailPanel()
  } else if (agiRef.value?.isOpen) {
    agiRef.value.togglePanel(false)
  }
}

const openInviteModal = () => {
  showInviteModal.value = true
}

const currentTime = ref(Date.now())
let countdownTimer = null

const showTaskTimePicker = ref(false)
const taskTimePickerValue = ref([])
const showGaiTimePicker = ref(false)
const gaiTimePickerValue = ref([])

const formatStringToArr = (str) => {
  if (!str) return []
  const d = new Date(str)
  const pad = n => String(n).padStart(2, '0')
  return [String(d.getFullYear()), pad(d.getMonth() + 1), pad(d.getDate())]
}

const formatArrToString = (arr) => {
  if (!arr || arr.length < 3) return null
  return new Date(arr[0], arr[1] - 1, arr[2], 23, 59, 59).toISOString()
}

const formatDisplayTime = (str) => {
  if (!str) return ''
  const d = new Date(str)
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

const getCountdown = (deadlineStr) => {
  if (!deadlineStr) return ''
  const now = currentTime.value
  const end = new Date(deadlineStr).getTime()
  const diff = end - now
  if (diff <= 0) return '已截止'
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))
  const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
  if (days > 0) return `剩余 ${days}天${hours}小时`
  if (hours > 0) return `剩余 ${hours}小时${mins}分`
  return `剩余 ${mins}分钟`
}

const currentCompRate = ref(0)
const currentScoreRate = ref(0)
const isTaskDetailLoading = ref(false)

const courseInfo = reactive({id: '', name: '', cover: '', teacher: teacherName.value})

const mapChaptersToLocal = (chapters) => chapters.map(ch => ({
  id: ch.chapter_id,
  order: ch.chapter_order,
  title: ch.chapter_title,
  expanded: true,
  sections: ch.sub_tasks.map(st => ({
    id: st.section_id,
    title: st.section_title,
    type: st.section_type,
    hasResource: !!st.resource_path,
    resourcePath: st.resource_path,
    description: st.description || '',
    is_completed: st.is_completed || false,
    learning_effect: st.learning_effect || 0
  }))
}))

const chapterList = ref([])
const taskList = ref([])
const gaiTaskList = ref([])
const studentList = ref([])
const pendingFiles = reactive({})

const genLocalId = () => `local_${Date.now()}_${Math.floor(Math.random() * 10000)}`


const toggleEditMode = async () => {
  if (isEditMode.value) {
    if (activeLeftTab.value === 'chapter') {
      isSaving.value = true
      const pendingKeys = Object.keys(pendingFiles)
      if (pendingKeys.length > 0) {
        const uploadPromises = pendingKeys.map(key => upload_resource(pendingFiles[key]).then(res => ({
          key,
          path: res.data.path
        })))
        const results = await Promise.all(uploadPromises)
        results.forEach(r => {
          for (const ch of chapterList.value) {
            const sec = ch.sections.find(s => s.localId === r.key)
            if (sec) {
              sec.resourcePath = r.path
              sec.hasResource = !!r.path
              break
            }
            delete pendingFiles[r.key]
          }
        })
      }
      const payload = chapterList.value.map((ch, index) => ({
        chapter_id: ch.id,
        chapter_title: ch.title,
        chapter_order: index + 1,
        sub_tasks: ch.sections.map((sec, sIndex) => ({
          section_id: sec.id,
          section_title: sec.title,
          section_type: sec.type,
          section_order: sIndex + 1,
          resource_path: sec.resourcePath,
          description: sec.description || ''
        }))
      }))
      const res = await update_chapters_batch(courseInfo.id, payload)
      chapterList.value = mapChaptersToLocal(res.data.chapters)
      showToast({message: '章节保存成功', type: 'success'})
      isSaving.value = false
    }
    isEditMode.value = false
  } else {
    isEditMode.value = true
    closeDetailPanel()
    showGaiTaskDetailPanel.value = false
  }
}

const handleDeleteCourse = () => {
  showConfirmDialog({title: '删除课程', message: '确定删除该课程吗？此操作不可恢复。'}).then(async () => {
    await delete_course(courseInfo.id)
    showToast({message: '课程已删除', type: 'success'})
    router.back()
  }).catch(() => {
  })
}

const selectedAnalysisStudentId = ref('')
const renderedAnalysisText = ref('')
const isStreaming = ref(false)
let streamTimer = null
const rawAnalysisRecords = ref([])

const analysisData = reactive({
  chapterDone: 0,
  chapterTotal: 0,
  taskDone: 0,
  taskTotal: 0,
  taskQuality: '0',
  gaiDone: 0,
  gaiTotal: 0
})
const analysisRates = reactive({chapterRate: 0, taskRate: 0, gaiRate: 0})
const currentAnalysisChapterRate = ref(0)
const currentAnalysisTaskRate = ref(0)
const currentAnalysisGaiRate = ref(0)

/**
 * 安全计算百分比，防止分母为0时产生 NaN 或 Infinity
 * @param {number} num - 分子
 * @param {number} den - 分母
 * @returns {number} 百分比整数 (0-100)
 */
const calcRate = (num, den) => den === 0 ? 0 : Math.round((num / den) * 100)

/**
 * 切换到学生学习分析视图并初始化数据
 * @returns {Promise<void>}
 */
const switchToAnalysis = async () => {
  activeLeftTab.value = 'analysis'
  analysisLoading.value = true
  if (rawAnalysisRecords.value.length === 0) {
    const res = await get_analysis_raw_records(courseInfo.id)
    rawAnalysisRecords.value = res.data.records
  }
  selectedAnalysisStudentId.value = 'all'
  calculateMetrics('all')
  const textRes = await get_analysis_ai_text_for_student_study(courseInfo.id, 'all')
  startStream(textRes.data.description, renderedAnalysisText, isStreaming)
  analysisLoading.value = false
}

const selectAnalysisStudent = async (val) => {
  selectedAnalysisStudentId.value = val
  calculateMetrics(val)
  const textRes = await get_analysis_ai_text_for_student_study(courseInfo.id, val)
  startStream(textRes.data.description, renderedAnalysisText, isStreaming)
}

const calculateMetrics = (targetId) => {
  let totalSections = 0
  chapterList.value.forEach(ch => totalSections += ch.sections.length)
  const totalTasks = taskList.value.length
  const totalGai = gaiTaskList.value.length
  let doneSections = 0, doneTasks = 0, doneGais = 0, totalScore = 0, validScoreCount = 0

  if (targetId === 'all') {
    const totalStudents = rawAnalysisRecords.value.length || 1
    rawAnalysisRecords.value.forEach(stu => {
      doneSections += stu.done_section_ids.length
      doneTasks += stu.done_task_ids.length
      doneGais += stu.done_gai_ids.length
      Object.values(stu.task_scores).forEach(score => {
        totalScore += score
        validScoreCount++
      })
    })
    doneSections = calcRate(doneSections, totalStudents * totalSections)
    doneTasks = calcRate(doneTasks, totalStudents * totalTasks)
    doneGais = calcRate(doneGais, totalStudents * totalGai)
  } else {
    const stuRecord = rawAnalysisRecords.value.find(r => r.student_id === targetId)
    if (stuRecord) {
      doneSections = calcRate(stuRecord.done_section_ids.length, totalSections)
      doneTasks = calcRate(stuRecord.done_task_ids.length, totalTasks)
      doneGais = calcRate(stuRecord.done_gai_ids.length, totalGai)
      Object.values(stuRecord.task_scores).forEach(score => {
        totalScore += score
        validScoreCount++
      })
    }
  }
  const taskQuality = validScoreCount > 0 ? totalScore / validScoreCount : 0
  Object.assign(analysisData, {
    chapterTotal: totalSections,
    chapterDone: doneSections,
    taskTotal: totalTasks,
    taskDone: doneTasks,
    taskQuality: taskQuality.toFixed(1),
    gaiTotal: totalGai,
    gaiDone: doneGais
  })
  analysisRates.chapterRate = doneSections
  analysisRates.taskRate = doneTasks
  analysisRates.gaiRate = doneGais
}

const editingChapterId = ref(null)
const toggleChapter = (idx) => chapterList.value[idx].expanded = !chapterList.value[idx].expanded

const insertChapter = (idx) => {
  chapterList.value.splice(idx, 0, {
    id: null,
    localId: genLocalId(),
    order: (chapterList.value.length + 1).toString(),
    title: '新章节',
    expanded: true,
    sections: []
  })
  editingChapterId.value = null
}

const deleteChapter = (idx) => {
  showConfirmDialog({message: '确认删除该章节及其所有内容？'}).then(() => chapterList.value.splice(idx, 1)).catch(() => {
  })
}

const deleteSection = (cIdx, sIdx) => {
  const removed = chapterList.value[cIdx].sections.splice(sIdx, 1)[0]
  if (removed && removed.localId && pendingFiles[removed.localId]) delete pendingFiles[removed.localId]
}

const showSectionModal = ref(false)
const currentSection = ref(null)
const targetChapterId = ref('')
const isSectionModalReadOnly = ref(false)

const sectionForm = reactive({
  title: '',
  type: 'video',
  description: '',
  fileUploaded: false,
  resourcePath: null
})
const sectionFileError = ref(false)
const fileInputRef = ref(null)
let pendingFile = null

const simulateUpload = () => {
  if (!isSectionModalReadOnly.value) {
    fileInputRef.value.click()
  }
}

const openSectionModal = (cId, section = null) => {
  targetChapterId.value = cId
  currentSection.value = section
  sectionFileError.value = false
  pendingFile = null
  if (section) {
    if (isEditMode.value) {
      isSectionModalReadOnly.value = true
    } else {
      isSectionModalReadOnly.value = false
    }
    sectionForm.title = section.title
    sectionForm.type = section.type
    sectionForm.fileUploaded = section.hasResource
    sectionForm.resourcePath = section.resourcePath
    sectionForm.description = section.description || ''
  } else {
    isSectionModalReadOnly.value = false
    sectionForm.title = ''
    sectionForm.type = 'video'
    sectionForm.description = ''
    sectionForm.fileUploaded = false
    sectionForm.resourcePath = null
  }
  showSectionModal.value = true
}

const handleFileChange = (event) => {
  const file = event.target.files[0]
  if (!file) return
  pendingFile = file
  sectionForm.fileUploaded = true
  sectionFileError.value = false
}

const saveSection = async () => {
  if (!sectionForm.title) return showToast({message: '请输入名称', type: 'fail'})
  if (!sectionForm.fileUploaded && !sectionForm.resourcePath) return sectionFileError.value = true
  let ch = chapterList.value.find(c => c.id === targetChapterId.value || c.localId === targetChapterId.value) || chapterList.value[chapterList.value.length - 1]

  if (currentSection.value) {
    currentSection.value.title = sectionForm.title
    currentSection.value.type = sectionForm.type
    currentSection.value.description = sectionForm.description || ''
    if (pendingFile) {
      if (!currentSection.value.localId) currentSection.value.localId = genLocalId()
      pendingFiles[currentSection.value.localId] = pendingFile
      currentSection.value.hasResource = true
      pendingFile = null
    }
  } else {
    const localId = genLocalId()
    const newSec = {
      id: null,
      localId,
      title: sectionForm.title,
      type: sectionForm.type,
      hasResource: !!sectionForm.fileUploaded,
      resourcePath: sectionForm.resourcePath,
      description: sectionForm.description || ''
    }
    ch.sections.push(newSec)
    if (pendingFile) {
      pendingFiles[localId] = pendingFile
      pendingFile = null
    }
  }
  showSectionModal.value = false
  sectionForm.title = ''
  sectionForm.description = ''
  sectionForm.fileUploaded = false
  sectionForm.resourcePath = null
}

// ==================== 任务组卷 ====================
const showTaskModal = ref(false)
const currentTask = ref(null)
const taskForm = reactive({title: '', questions: [], deadline: null})

const createBlankQuestion = () => {
  const ts = Date.now()
  return {
    id: `q_${ts}`,
    type: 'single',
    title: '',
    options: [{id: `opt_${ts}_0`, content: ''}, {id: `opt_${ts}_1`, content: ''}, {
      id: `opt_${ts}_2`,
      content: ''
    }, {id: `opt_${ts}_3`, content: ''}],
    correctAnswerId: '',
    correctAnswerIds: [],
    referAnswer: '',
    hasError: false,
    isShaking: false
  }
}

const getCurrentTimeArr = () => {
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  return [String(now.getFullYear()), pad(now.getMonth() + 1), pad(now.getDate())]
}

const openTaskModal = async (task = null) => {
  currentTask.value = task
  showTaskModal.value = true
  if (task) {
    isTaskDetailLoading.value = true
    taskForm.title = task.task_title
    taskForm.questions = []
    taskForm.deadline = task.deadline
    taskTimePickerValue.value = task.deadline ? formatStringToArr(task.deadline) : getCurrentTimeArr()
    try {
      const res = await get_task_detail_for_edit(courseInfo.id, task.task_id)
      const detailData = res.data
      if (detailData.quiz && detailData.answer) {
        taskForm.questions = detailData.quiz.map((q, index) => {
          const a = detailData.answer[index]
          const baseQuestion = {
            id: q.question_id,
            type: q.type,
            title: q.title,
            options: q.options.map(opt => ({id: opt.id, content: opt.content})),
            correctAnswerId: '',
            correctAnswerIds: [],
            referAnswer: '',
            hasError: false,
            isShaking: false
          }
          if (q.type === 'single') baseQuestion.correctAnswerId = a.correct_answer[0]
          if (q.type === 'multiple') baseQuestion.correctAnswerIds = a.correct_answer
          if (q.type === 'judge') {
            baseQuestion.correctAnswerId = a.correct_answer[0]
            baseQuestion.options = [{id: 'true', content: '正确'}, {id: 'false', content: '错误'}]
          }
          if (q.type === 'subjective') baseQuestion.referAnswer = a.correct_answer
          return baseQuestion
        })
      } else {
        taskForm.questions = [createBlankQuestion()]
      }
    } catch (error) {
      showToast({message: '获取任务详情失败', type: 'fail'})
      taskForm.questions = [createBlankQuestion()]
    } finally {
      isTaskDetailLoading.value = false
    }
  } else {
    taskForm.title = ''
    taskForm.deadline = null
    taskTimePickerValue.value = getCurrentTimeArr()
    taskForm.questions = [createBlankQuestion()]
  }
}

const addQuestion = (idx) => taskForm.questions.splice(idx + 1, 0, createBlankQuestion())

const toggleCorrectAnswer = (q, optId) => {
  const i = q.correctAnswerIds.indexOf(optId)
  if (i > -1) q.correctAnswerIds.splice(i, 1)
  else q.correctAnswerIds.push(optId)
}

const scrollToQuestion = async (index) => {
  taskForm.questions[index].isShaking = true
  setTimeout(() => {
    taskForm.questions[index].isShaking = false
  }, 600)

  await nextTick()
  const element = document.getElementById(`question-card-${index}`)
  if (element) {
    element.scrollIntoView({behavior: 'smooth', block: 'center'})
  }
}

const saveTask = async () => {
  if (!taskForm.title) return showToast({message: '请输入任务名称', type: 'fail'})
  if (!taskForm.deadline) return showToast({message: '请设置截止时间', type: 'fail'})

  taskForm.questions.forEach(q => {
    q.hasError = false
    q.isShaking = false
  })

  let errorCount = 0
  let firstErrorIndex = -1

  taskForm.questions.forEach((q, i) => {
    if (!q.title.trim()) {
      q.hasError = true
      errorCount++
      if (firstErrorIndex === -1) firstErrorIndex = i
    }
  })
  if (errorCount > 0) {
    showToast({
      message: `题目内容不能为空\n有${errorCount}个题目内容为空`,
      type: 'fail',
      duration: 3000,
      className: 'validation-toast'
    })
    scrollToQuestion(firstErrorIndex)
    return
  }

  errorCount = 0
  firstErrorIndex = -1
  taskForm.questions.forEach((q, i) => {
    if (q.type === 'single' || q.type === 'multiple') {
      const hasOptionError = q.options.some(opt => !opt.content.trim())
      if (hasOptionError) {
        q.hasError = true
        errorCount++
        if (firstErrorIndex === -1) firstErrorIndex = i
      }
    }
  })
  if (errorCount > 0) {
    showToast({
      message: `选项内容不能为空\n有${errorCount}个题目的选项有空`,
      type: 'fail',
      duration: 3000,
      className: 'validation-toast'
    })
    scrollToQuestion(firstErrorIndex)
    return
  }

  errorCount = 0
  firstErrorIndex = -1
  taskForm.questions.forEach((q, i) => {
    let hasAnswerError = false
    if (q.type === 'single') {
      if (!q.correctAnswerId) hasAnswerError = true
    } else if (q.type === 'multiple') {
      if (q.correctAnswerIds.length === 0) hasAnswerError = true
    } else if (q.type === 'judge') {
      if (!q.correctAnswerId) hasAnswerError = true
    } else if (q.type === 'subjective') {
      if (!q.referAnswer.trim()) hasAnswerError = true
    }

    if (hasAnswerError) {
      q.hasError = true
      errorCount++
      if (firstErrorIndex === -1) firstErrorIndex = i
    }
  })
  if (errorCount > 0) {
    showToast({
      message: `需要指定题目的正确答案\n有${errorCount}个题目的答案未指定`,
      type: 'fail',
      duration: 3000,
      className: 'validation-toast'
    })
    scrollToQuestion(firstErrorIndex)
    return
  }

  const quiz = taskForm.questions.map(q => ({
    question_id: q.id,
    type: q.type,
    title: q.title,
    options: (q.type === 'single' || q.type === 'multiple') ? q.options.map(opt => ({
      id: opt.id, content: opt.content
    })) : []
  }))

  const answer = taskForm.questions.map(q => {
    if (q.type === 'single') return {question_id: q.id, type: q.type, correct_answer: [q.correctAnswerId]}
    if (q.type === 'multiple') return {question_id: q.id, type: q.type, correct_answer: [...q.correctAnswerIds]}
    if (q.type === 'judge') return {question_id: q.id, type: q.type, correct_answer: [q.correctAnswerId]}
    if (q.type === 'subjective') return {question_id: q.id, type: q.type, correct_answer: q.referAnswer}
    return {question_id: q.id, type: q.type, correct_answer: []}
  })

  const payload = {task_title: taskForm.title, quiz, answer, deadline: taskForm.deadline}
  let resTask
  if (currentTask.value) {
    resTask = await update_task(courseInfo.id, currentTask.value.task_id, payload)
    const idx = taskList.value.findIndex(t => t.task_id === currentTask.value.task_id)
    if (idx !== -1) taskList.value[idx] = resTask.data
  } else {
    resTask = await create_task(courseInfo.id, payload)
    taskList.value.push(resTask.data)
  }
  showToast({message: '保存成功', type: 'success'})
  closeTaskModal()
  taskForm.title = ''
  taskForm.questions = []
}

const deleteTask = (idx, type) => {
  showConfirmDialog({message: '确认删除该任务？'}).then(async () => {
    if (type === 'task') {
      await delete_task(courseInfo.id, taskList.value[idx].task_id)
      taskList.value.splice(idx, 1)
    } else if (type === 'gai-task') {
      await delete_gai_task(courseInfo.id, gaiTaskList.value[idx].analysis_task_id)
      gaiTaskList.value.splice(idx, 1)
      showToast({message: '人机交互任务已删除', type: 'success'})
    }
  }).catch(() => {
  })
}

const gaiTaskStudentList = ref([])
const showGaiTaskModal = ref(false)
const currentGaiTask = ref(null)
const gaiTaskForm = reactive({title: '', desc: '', analysisReq: '', scoreRule: '', deadline: null})

const openGaiTaskModal = (task) => {
  currentGaiTask.value = task
  if (task) {
    gaiTaskForm.title = task.analysis_task_title
    gaiTaskForm.desc = task.task_description
    gaiTaskForm.analysisReq = task.analysis_description
    gaiTaskForm.scoreRule = task.evaluation_criterion
    gaiTaskForm.deadline = task.deadline
    gaiTimePickerValue.value = task.deadline ? formatStringToArr(task.deadline) : getCurrentTimeArr()
  } else {
    gaiTaskForm.title = ''
    gaiTaskForm.desc = ''
    gaiTaskForm.analysisReq = ''
    gaiTaskForm.scoreRule = ''
    gaiTaskForm.deadline = null
    gaiTimePickerValue.value = getCurrentTimeArr()
  }
  showGaiTaskModal.value = true
}

const saveGaiTask = async () => {
  if (!gaiTaskForm.deadline) return showToast({message: '请设置截止时间', type: 'fail'})
  if (!gaiTaskForm.title.trim()) return showToast({message: '请输入人机交互任务标题', type: 'fail'})
  if (!gaiTaskForm.desc.trim()) return showToast({message: '请输入任务描述', type: 'fail'})
  if (!gaiTaskForm.analysisReq.trim()) return showToast({message: '请输入对话分析需求', type: 'fail'})
  if (!gaiTaskForm.scoreRule.trim()) return showToast({message: '请输入评分标准', type: 'fail'})
  const payload = {
    analysis_task_title: gaiTaskForm.title,
    task_description: gaiTaskForm.desc,
    analysis_description: gaiTaskForm.analysisReq,
    evaluation_criterion: gaiTaskForm.scoreRule,
    deadline: gaiTaskForm.deadline
  }
  let resTask
  if (currentGaiTask.value) {
    resTask = await update_gai_task(courseInfo.id, currentGaiTask.value.analysis_task_id, payload)
    const idx = gaiTaskList.value.findIndex(t => t.analysis_task_id === currentGaiTask.value.analysis_task_id)
    if (idx !== -1) gaiTaskList.value[idx] = resTask.data
  } else {
    resTask = await create_gai_task(courseInfo.id, payload)
    gaiTaskList.value.push(resTask.data)
  }
  showToast({message: '保存成功', type: 'success'})
  closeGaiTaskModal()
  gaiTaskForm.title = ''
  gaiTaskForm.desc = ''
  gaiTaskForm.analysisReq = ''
  gaiTaskForm.scoreRule = ''
  gaiTaskForm.deadline = null
}

const showDetailPanel = ref(false)
const detailType = ref('section')
const detailTargetName = ref('')
const detailData = reactive({
  completionRate: 0,
  scoreRate: 0,
  score: 0,
  completedStudents: [],
  uncompletedStudents: []
})

const handleSectionClick = (section, chapter) => {
  if (isEditMode.value) {
    openSectionModal(chapter.localId || chapter.id, section)
    return
  }
  openDetailPanel('section', section.title, section.id, chapter.title)
}

const handleTaskClick = (task) => {
  if (isEditMode.value) openTaskModal(task)
  else openDetailPanel('task', task.task_title, task.task_id, '')
}

const formatChaptersContext = () => chapterList.value.map((ch, idx) => {
  const sectionTexts = ch.sections.map(sec => ` - ${sec.title}`).join('\n')
  return `${idx + 1}. ${ch.title}\n${sectionTexts}`
}).join('\n')

const formatStudentsContext = (records, type) => {
  const total = records.length
  const completedRecords = records.filter(r => r.is_completed)
  const uncompletedRecords = records.filter(r => !r.is_completed)
  const doneCount = completedRecords.length
  const avgScore = doneCount > 0 ? (completedRecords.reduce((sum, r) => sum + r.score, 0) / doneCount).toFixed(1) : 0
  const undoneCount = uncompletedRecords.length
  const undoneNames = undoneCount > 0 ? uncompletedRecords.map(r => r.student_name).join('、') : '无'
  const scoreLabel = type === 'section' ? '平均学习质量' : '平均任务得分'
  return `共${total}人。已完成${doneCount}人（${scoreLabel}：${avgScore}分）；未完成${undoneCount}人（名单：${undoneNames}）。`
}

const formatQuizContext = (quiz) => {
  if (!quiz || quiz.length === 0) return '无测试题目数据'
  const typeMap = {single: '单选题', multiple: '多选题', judge: '判断题', subjective: '主观题'}
  return quiz.map((q, idx) => {
    const typeLabel = typeMap[q.type] || '未知类型'
    let text = `${idx + 1}. [${typeLabel}] ${q.title}`
    if (q.options && q.options.length > 0) {
      const optionsText = q.options.map((opt, optIdx) => ` ${String.fromCharCode(65 + optIdx)}.${opt.content}`).join('\n')
      text += '\n' + optionsText
    }
    return text
  }).join('\n\n')
}

const openDetailPanel = async (type, title, targetId, chapterTitle = '') => {
  detailType.value = type
  detailTargetName.value = title
  detailData.completionRate = 0
  detailData.scoreRate = 0
  detailData.completedStudents = []
  detailData.uncompletedStudents = []
  currentCompRate.value = 0
  currentScoreRate.value = 0
  showDetailPanel.value = true
  const apiType = type === 'section' ? 'section' : 'task'
  let records = []
  if (agiRef.value) {
    agiRef.value.togglePanel(true)
    if (type === 'task') {
      const [detailRes, taskEditRes] = await Promise.all([get_completion_details(courseInfo.id, apiType, targetId), get_task_detail_for_edit(courseInfo.id, targetId)])
      records = detailRes.data.student_records
      const quizData = taskEditRes.data.quiz || []
      const chaptersOutline = formatChaptersContext()
      const studentsDataText = formatStudentsContext(records, type)
      const quizText = formatQuizContext(quizData)
      const taskPrompt = `【角色设定】你是一位严谨、专业的教学测评分析师。 【核心原则】 1. 绝对禁止脑补：所有分析必须100%依赖提供的“学情聚合数据”和“测试题目内容”，严禁凭空捏造具体学生的错题情况。 2. 拒绝套路化表达：严禁使用“紧急干预”、“核心病灶”、Emoji符号及Markdown表格。语气应客观、冷峻，聚焦于测评数据背后的教学意义。 3. 隐去标准答案：你看到的题目不包含正确答案，请根据学生的整体得分率和题目表面特征进行宏观推断。 【分析上下文】 - 课程名称：${courseInfo.name} - 课程章节大纲（用于定位任务考查进度）： \n${chaptersOutline} - 当前任务：${title} - 任务学情聚合数据： \n${studentsDataText} - 任务测试题目原文： \n${quizText} 【输出结构要求】 请按以下维度输出专业分析： 1. 【测评结果画像】：基于完成率和平均分，用专业术语描绘本次测试的整体水平（如：区分度不足、整体达标、两极分化严重等）。 2. 【考查维度与得分推演】：对照“课程章节大纲”的进度，分析本次题目主要考查了哪些知识点。结合“整体得分率”，推断学生在这些特定知识点上的掌握盲区或误区可能是什么。 3. 【讲评与干预策略】：基于上述推断，给出2条针对该任务后续讲评的具体策略（如：针对得分率最低的题型重点梳理、设计变式训练等）。`
      agiRef.value.sendSilentMessage(taskPrompt)
    } else {
      const res = await get_completion_details(courseInfo.id, apiType, targetId)
      records = res.data.student_records
      const chaptersOutline = formatChaptersContext()
      const studentsDataText = formatStudentsContext(records, type)
      const sectionPrompt = `【角色设定】你是一位严谨、务实且经验丰富的教学数据教研员。 【核心原则】 1. 绝对禁止脑补：所有分析必须100%依赖提供的“聚合统计数据”，严禁猜测平台故障、学生心理或未提供的数据细节。 2. 拒绝套路化表达：严禁使用“紧急干预”、“核心病灶”、Emoji符号及Markdown表格。语气应专业、中肯，像一位资深教研员在写评课记录。 3. 禁止罗列名单：不要在回复中重复未完成学生的具体姓名，只需将其视为“未完成群体”进行整体分析。 【分析上下文】 - 课程名称：${courseInfo.name} - 授课教师：${teacherName.value} - 课程完整章节大纲： \n${chaptersOutline} - 当前定位：章节「${chapterTitle}」下的 小节「${title}」 - 本小节学情聚合数据： \n${studentsDataText} 【输出结构要求】 请按以下维度输出专业分析，避免机械播报，注重教学逻辑的展现： 1. 【学情特征】：提炼数据中最显著的特征（如：完成度瓶颈、得分两极分化、整体掌握优良等），用专业的教研语言描述当前状态。 2. 【归因推断】：基于上述数据特征，结合“当前小节在整体大纲中的位置”，给出最合乎逻辑的1-2种客观推断（注意：推断必须基于教学内容规律，而非主观臆测）。 3. 【后续教学策略】：针对推断，给出2条具体、可落地的教学改进策略（如：在后续某章节如何承上启下、如何针对未完成群体设计补测或脚手架等）。`
      agiRef.value.sendSilentMessage(sectionPrompt)
    }
  } else {
    const res = await get_completion_details(courseInfo.id, apiType, targetId)
    records = res.data.student_records
  }
  const completedRecords = records.filter(r => r.is_completed)
  const uncompletedRecords = records.filter(r => !r.is_completed)
  const totalStudents = records.length
  const compRate = totalStudents > 0 ? (completedRecords.length / totalStudents) * 100 : 0
  const validScores = completedRecords.map(r => r.score)
  const avgScore = validScores.length > 0 ? validScores.reduce((sum, s) => sum + s, 0) / validScores.length : 0
  detailData.completionRate = compRate
  detailData.scoreRate = avgScore
  detailData.completedStudents = completedRecords.map(r => ({
    name: r.student_name,
    score: r.score.toFixed(1),
    class_name: r.class_name
  }))
  detailData.uncompletedStudents = uncompletedRecords.map(r => ({name: r.student_name, class_name: r.class_name}))
}

const closeDetailPanel = () => {
  showDetailPanel.value = false
  if (agiRef.value) agiRef.value.togglePanel(false)
}

const showGaiTaskDetailPanel = ref(false)
const selectedGaiStudentId = ref('')
const renderedGaiAnalysisText = ref('')
const isGaiStreaming = ref(false)
const isGaiDetailLoading = ref(false)

const handleGaiTaskClick = async (gt) => {
  if (isEditMode.value) return openGaiTaskModal(gt)
  currentGaiTask.value = gt
  showGaiTaskDetailPanel.value = true
  selectedGaiStudentId.value = ''
  currentGaiTask.value.chatHistory = []
  renderedGaiAnalysisText.value = ''
  isGaiStreaming.value = false
  const res = await get_gai_task_students(courseInfo.id, gt.analysis_task_id)
  gaiTaskStudentList.value = res.data.students
  if (gaiTaskStudentList.value.length > 0) {
    await selectGaiStudent(gaiTaskStudentList.value[0].id)
  } else {
    renderedGaiAnalysisText.value = '暂无学生参与该任务'
  }
}

const selectGaiStudent = async (id) => {
  if (isGaiDetailLoading.value) return
  const currentStudent = gaiTaskStudentList.value.find(s => s.id === id)
  if (currentStudent && !currentStudent.is_completed) {
    selectedGaiStudentId.value = id
    currentGaiTask.value.chatHistory = []
    renderedGaiAnalysisText.value = '没有提交，无法分析'
    isGaiStreaming.value = false
    clearInterval(streamTimer)
    return
  }
  isGaiDetailLoading.value = true
  selectedGaiStudentId.value = id
  currentGaiTask.value.chatHistory = []
  renderedGaiAnalysisText.value = '正在获取分析数据...'
  isGaiStreaming.value = false
  clearInterval(streamTimer)
  const res = await get_gai_student_analysis(courseInfo.id, currentGaiTask.value.analysis_task_id, id)
  currentGaiTask.value.chatHistory = res.data.chat_history
  const text = res.data.analysis_text
  startStream(text, renderedGaiAnalysisText, isGaiStreaming)
  isGaiDetailLoading.value = false
}

const startStream = (fullText, targetRef, flagRef) => {
  clearInterval(streamTimer)
  flagRef.value = true
  const targetDuration = 7500
  const interval = 30
  const totalSteps = targetDuration / interval
  const chunkSize = Math.max(1, Math.ceil(fullText.length / totalSteps))
  let index = 0
  streamTimer = setInterval(() => {
    const partial = fullText.slice(0, index)
    targetRef.value = renderMd(partial)
    index += chunkSize
    if (index >= fullText.length) {
      targetRef.value = renderMd(fullText)
      clearInterval(streamTimer)
      flagRef.value = false
    }
  }, interval)
}

// ==================== 班级分组逻辑 ====================
const classExpandedState = reactive({})

const groupStudentsByClass = (students, nameKey = 'name') => {
  if (!students) return []
  const groupMap = new Map()
  students.forEach(stu => {
    const className = stu.class_name
    if (!groupMap.has(className)) {
      groupMap.set(className, [])
    }
    groupMap.get(className).push(stu)
  })
  return Array.from(groupMap, ([class_name, students]) => ({class_name, students}))
}

const toggleClassExpand = (prefix, className) => {
  const key = `${prefix}${className}`
  classExpandedState[key] = !classExpandedState[key]
}

const isClassExpanded = (prefix, className) => {
  const key = `${prefix}${className}`
  return !!classExpandedState[key]
}

onMounted(async () => {
  const courseId = route.params.course_id
  courseInfo.id = courseId
  if (!courseId) {
    showToast({message: '缺少课程ID', type: 'fail'})
    countdownTimer = setInterval(() => {
      currentTime.value = Date.now()
    }, 60000)
    return
  }
  const detail = await get_course_detail(courseId)
  const {course_name, course_cover, invited_code, is_invitation_valid} = detail.data
  courseInfo.name = course_name
  courseInfo.cover = course_cover.startsWith('http') ? course_cover : `${import.meta.env.VITE_RESOURCE_BASE_URL}${course_cover}`
  inviteCode.value = invited_code
  isInvitationValid.value = is_invitation_valid
  const chaptersRes = await get_chapters(courseId)
  chapterList.value = mapChaptersToLocal(chaptersRes.data.chapters)
  const tasksRes = await get_tasks(courseId)
  taskList.value = tasksRes.data.tasks
  const gaiTasksRes = await get_gai_tasks(courseId)
  gaiTaskList.value = gaiTasksRes.data.gai_tasks
  const stuRes = await get_course_students(courseId)
  studentList.value = stuRes.data.students.map(item => ({id: item.id, name: item.name, class_name: item.class_name}))
  countdownTimer = setInterval(() => {
    currentTime.value = Date.now()
  }, 60000)
})

/**
 * 确认选择任务截止时间
 */
const confirmTaskTime = () => {
  taskForm.deadline = formatArrToString(taskTimePickerValue.value)
  showTaskTimePicker.value = false
}

/**
 * 清除任务截止时间
 */
const clearTaskTime = () => {
  taskForm.deadline = null
  taskTimePickerValue.value = []
  showTaskTimePicker.value = false
}

/**
 * 确认选择人机交互任务截止时间
 */
const confirmGaiTime = () => {
  gaiTaskForm.deadline = formatArrToString(gaiTimePickerValue.value)
  showGaiTimePicker.value = false
}

/**
 * 清除人机交互任务截止时间
 */
const clearGaiTime = () => {
  gaiTaskForm.deadline = null
  gaiTimePickerValue.value = []
  showGaiTimePicker.value = false
}

/**
 * 关闭任务编辑弹窗并重置内部时间选择器状态，防止状态残留
 */
const closeTaskModal = () => {
  showTaskTimePicker.value = false
  showTaskModal.value = false
}

/**
 * 关闭人机交互任务编辑弹窗并重置内部时间选择器状态，防止状态残留
 */
const closeGaiTaskModal = () => {
  showGaiTimePicker.value = false
  showGaiTaskModal.value = false
}

/**
 * 处理时间选择器PC端鼠标滚轮事件，将其转换为选项点击以触发原生滚动动画
 * @param {WheelEvent} e - 鼠标滚轮事件对象
 */
const handleTimePickerWheel = (e) => {
  const column = e.target.closest('.van-picker-column')
  if (!column) return
  const selectedItem = column.querySelector('.van-picker-column__item--selected')
  if (!selectedItem) return
  let targetItem = null
  if (e.deltaY < 0) {
    targetItem = selectedItem.previousElementSibling
  } else if (e.deltaY > 0) {
    targetItem = selectedItem.nextElementSibling
  }
  if (targetItem) {
    targetItem.click()
  }
}

onUnmounted(() => {
  if (streamTimer) clearInterval(streamTimer)
  if (countdownTimer) clearInterval(countdownTimer)
})
</script>
<style>
.validation-toast {
  width: max-content !important;
  min-width: unset !important;
  max-width: 90vw !important;
  text-align: center !important;
}
</style>

<style scoped src="../../styles/views/teacher/CourseTeacher.css"></style>
