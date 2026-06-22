import {fileURLToPath, URL} from 'node:url'

import {defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import postcsspxtoviewport from 'postcss-px-to-viewport-8-plugin'

// https://vite.dev/config/
export default defineConfig({
    build: {
        outDir: "../frontend/dist",     // 直接输出到 Nginx 挂载的路径
        emptyOutDir: true,
    },
    plugins: [
        vue(),
        vueDevTools(),
    ],
    resolve: {
        alias: {
            '@': fileURLToPath(new URL('./src', import.meta.url))
        },
    },
    css: {
        postcss: {
            plugins: [
                postcsspxtoviewport({
                    unitToConvert: 'px',      // 需要转换的单位
                    viewportWidth: 1380,      // 视窗的宽度，对应 11寸平板横屏设计稿的宽度 (可根据实际设计稿宽度调整，如 1024 或 1194)
                    unitPrecision: 5,         // 指定 `px` 转换为视窗单位值的小数位数
                    propList: ['*', '!backdrop-filter', '!-webkit-backdrop-filter'],  // 能转化为 vw 的属性列表，* 代表所有属性，排除 backdrop-filter 避免 blur() 失效
                    viewportUnit: 'vw',       // 指定需要转换成的视窗单位，建议使用 vw
                    fontViewportUnit: 'vw',   // 字体使用的视口单位
                    selectorBlackList: ['ignore-scale'], // 指定不转换为视窗单位的类名 (如果你有某个元素不想缩放，给它加这个class)
                    minPixelValue: 1,         // 小于或等于 1px 不转换 (通常 1px 的边框不需要缩放)
                    mediaQuery: false,        // 允许在媒体查询中转换 `px`
                    replace: true,            // 是否直接更换属性值，而不添加备用属性
                    exclude: [],              // 忽略某些文件夹下的文件或特定文件
                    landscape: false          // 是否添加根据 landscapeWidth 生成的媒体查询条件
                })
            ]
        }
    },
})
