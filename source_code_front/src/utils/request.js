// src/common/request.js
import axios from "axios";
import {showToast} from "vant";  // ：统一错误提示

const request = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || "/",
    timeout: 15000,
    withCredentials: true,
});

// 请求拦截（保持不变）
request.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem("token");
        if (token) config.headers.Authorization = `Bearer ${token}`;
        return config;
    },
    (error) => Promise.reject(error)
);

// 响应拦截：成功时直接返回 data，失败时统一处理并用 Toast 提示用户
request.interceptors.response.use(
    (response) => response.data,
    (error) => {
        // 请求被取消时不提示（比如组件卸载时的自动取消）
        if (axios.isCancel(error)) {
            console.log('请求已取消', error.message);
            return Promise.reject(error);
        }

        // 调用方通过 skipToast 配置跳过全局提示（由页面自行处理错误展示，如登录页行内错误）
        if (error.config?.skipToast) {
            return Promise.reject(error);
        }

        // 服务器有响应
        if (error.response) {
            const {status} = error.response;
            const serverMsg = error.response.data?.message || '请求失败';

            switch (status) {
                case 400:
                    showToast(serverMsg || '请求参数有误');
                    break;
                case 401:
                    showToast(serverMsg || '登录已过期，请重新登录');
                    localStorage.clear();
                    setTimeout(() => {
                        const loginPath = window.location.pathname.startsWith('/admin') ? '/admin/login' : '/';
                        if (window.location.pathname !== loginPath) {
                            window.location.href = loginPath;
                        }
                    }, 2000);
                    break;
                case 403:
                    break;
                case 404:
                    showToast('请求的资源不存在');
                    break;
                case 500:
                    showToast('服务器内部错误');
                    break;
                default:
                    showToast(serverMsg);
            }
        } else if (error.code === 'ECONNABORTED') {
            // 超时
            showToast('请求超时，请检查网络后重试');
        } else if (error.request) {
            // 网络异常
            showToast('网络异常，请检查网络连接');
        } else {
            // 其他错误
            showToast(error.message || '请求失败');
        }

        return Promise.reject(error);
    }
);

export default request;