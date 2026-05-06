import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 15000,
})

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message =
      error?.response?.data?.detail ||
      error?.message ||
      '请求失败'
    return Promise.reject(new Error(message))
  },
)

export default client
