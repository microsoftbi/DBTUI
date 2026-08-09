import axios from 'axios'
import { ElMessage } from 'element-plus'

// 通过 vite 代理访问后端，统一配置 baseURL
const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 统一错误提示
http.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail =
      error.response?.data?.detail ?? error.message ?? '请求失败，请重试'
    ElMessage.error(typeof detail === 'string' ? detail : '请求失败，请重试')
    return Promise.reject(error)
  },
)

export default http
