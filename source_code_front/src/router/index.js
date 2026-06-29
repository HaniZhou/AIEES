import {createRouter, createWebHistory} from 'vue-router'

const routes = [
    // ================= 基础路由 =================
    {
        path: '/',
        name: 'Login',
        component: () => import('../views/Login.vue'),
        meta: {title: '系统登录', requiresAuth: false}
    },
    // 新增：管理员登录路由
    {
        path: '/admin/login',
        name: 'AdminLogin',
        component: () => import('../views/admin/AdminLogin.vue'),
        meta: {title: '管理员登录', requiresAuth: false}
    },

    // ================= 学生端路由 =================
    {
        path: '/index',
        name: 'StudentIndex',
        component: () => import('../views/student/Index.vue'),
        meta: {title: '学生首页', requiresAuth: true, role: 'student'}
    },
    {
        path: '/resources',
        name: 'StudentResources',
        component: () => import('../views/student/Resources.vue'),
        meta: {title: '课程中心', requiresAuth: true, role: 'student'}
    },
    {
        path: '/course/:courseId',
        name: 'CourseStu',
        component: () => import('../views/student/CourseStu.vue'),
        meta: {title: '课程详情', requiresAuth: true, role: 'student'}
    },
    {
        path: '/course/study',
        name: 'StudentStudy',
        component: () => import('../views/student/StudentStudy.vue'),
        meta: {title: '学生学习', requiresAuth: true, role: 'student'}
    },
    {
        path: '/course/task',
        name: 'TaskDetail',
        component: () => import('../views/student/TaskDetail.vue'),
        meta: {title: '任务作答', requiresAuth: true, role: 'student'}
    },

    // ================= 教师端路由 =================
    {
        path: '/teacher/index',
        name: 'TeacherIndex',
        component: () => import('../views/teacher/IndexTeacher.vue'),
        meta: {title: '教师首页', requiresAuth: true, role: 'teacher'}
    },
    {
        path: '/teacher/resources',
        name: 'CourseManagement',
        component: () => import('../views/teacher/ResourceManage.vue'),
        meta: {title: '课程中心', requiresAuth: true, role: 'teacher'}
    },
    {
        path: '/teacher/course/:course_id',
        name: 'CourseTeacher',
        component: () => import('../views/teacher/CourseTeacher.vue'),
        meta: {title: '课程管理与编辑', requiresAuth: true, role: 'teacher'}
    },

    // ================= 管理员端路由 =================
    {
        path: '/admin/manage',
        name: 'AdminManagement',
        component: () => import('../views/admin/AdminManagement.vue'),
        meta: {title: '系统管理后台', requiresAuth: true, role: 'admin'}
    },

    {
        path: '/:pathMatch(.*)*',
        redirect: '/'
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

// ================= 全局路由守卫 =================
router.beforeEach((to, from, next) => {
    if (to.meta.title) {
        document.title = to.meta.title
    }

    const token = localStorage.getItem('token')
    const userRole = localStorage.getItem('role')
    // 新增：把 admin 加入合法角色白名单
    const validRoles = ['student', 'teacher', 'admin']

    if (to.meta.requiresAuth !== false) {
        if (!token || !validRoles.includes(userRole)) {
            // 如果访问的是 /admin/manage 被拦截，重定向到管理员登录页
            if (to.path.startsWith('/admin')) {
                return next({name: 'AdminLogin', query: {redirect: to.fullPath}})
            }
            return next({name: 'Login', query: {redirect: to.fullPath}})
        }

        if (to.meta.role && to.meta.role !== userRole) {
            // 根据不同角色退回对应的首页
            if (userRole === 'admin') return next('/admin/manage')
            return next(userRole === 'teacher' ? '/teacher/index' : '/index')
        }

        return next()

    } else {
        // 如果已登录，且访问的是 Login 或 AdminLogin
        if (token && validRoles.includes(userRole) && (to.name === 'Login' || to.name === 'AdminLogin')) {
            if (userRole === 'admin') return next('/admin/manage')
            return next(userRole === 'teacher' ? '/teacher/index' : '/index')
        }

        return next()
    }
})

export default router