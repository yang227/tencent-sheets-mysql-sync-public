import axios from 'axios'

const baseURL = '/api/sync'

export default {
  // 获取所有同步任务
  getTasks() {
    return axios.get(`${baseURL}/tasks`)
  },

  // 获取单个同步任务
  getTask(id) {
    return axios.get(`${baseURL}/tasks/${id}`)
  },

  // 创建同步任务
  createTask(data) {
    return axios.post(`${baseURL}/tasks`, data)
  },

  // 更新同步任务
  updateTask(id, data) {
    return axios.put(`${baseURL}/tasks/${id}`, data)
  },

  // 删除同步任务
  deleteTask(id) {
    return axios.delete(`${baseURL}/tasks/${id}`)
  },

  // 执行同步任务
  executeTask(id) {
    return axios.post(`${baseURL}/tasks/${id}/execute`)
  },

  // 停止同步任务
  stopTask(id) {
    return axios.post(`${baseURL}/tasks/${id}/stop`)
  },

  // 获取同步任务执行历史
  getTaskHistory(id, params) {
    return axios.get(`${baseURL}/tasks/${id}/history`, { params })
  },

  // 获取同步任务统计信息
  getTaskStats(id) {
    return axios.get(`${baseURL}/tasks/${id}/stats`)
  },

  // 获取所有任务实时监控数据
  getMonitorData() {
    return axios.get(`${baseURL}/monitor`)
  },

  // 获取仪表盘数据
  getDashboard() {
    return axios.get(`${baseURL}/dashboard`)
  }
}
