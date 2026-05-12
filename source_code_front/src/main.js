import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

// 引入 Vant UI 及其样式
import Vant from 'vant'
import 'vant/lib/index.css'

// 引入全局 CSS 规范 (包含颜色变量、重置样式等)
import './styles/global.css'

// 创建 Vue 实例
const app = createApp(App)

// 注册插件
app.use(createPinia()) // 状态管理
app.use(router)        // 路由管理
app.use(Vant)          // Vant UI 组件库

// 挂载到 index.html 的 #app 节点
app.mount('#app')