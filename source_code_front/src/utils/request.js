// src/utils/request.js
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

        // 服务器有响应
        if (error.response) {
            const {status} = error.response;
            const serverMsg = error.response.data?.message || '请求失败';

            switch (status) {
                case 400:
                    showToast(serverMsg || '请求参数有误');
                    break;
                case 401:
                    localStorage.clear();
                    // 延迟跳转，让用户看到提示
                    setTimeout(() => {
                        if (window.location.pathname !== '/') {
                            showToast('登录已过期，请重新登录');
                            window.location.href = '/';
                        }
                    }, 2000);
                    showToast('用户或者密码错误');
                    break;
                case 403:
                    showToast('没有权限进行此操作');
                    //跳转回上级页面
                    setTimeout(() => {
                        window.history.back();
                    }, 2000);
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