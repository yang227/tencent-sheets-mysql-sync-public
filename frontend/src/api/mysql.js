import axios from 'axios'

const baseURL = '/api/mysql-configs'

export default {
  // 获取所有MySQL配置
  getConfigs() {
    return axios.get(`${baseURL}`)
  },

  // 获取单个MySQL配置
  getConfig(id) {
    return axios.get(`${baseURL}/${id}`)
  },

  // 创建MySQL配置
  createConfig(data) {
    return axios.post(`${baseURL}`, data)
  },

  // 更新MySQL配置
  updateConfig(id, data) {
    return axios.put(`${baseURL}/${id}`, data)
  },

  // 删除MySQL配置
  deleteConfig(id) {
    return axios.delete(`${baseURL}/${id}`)
  },

  // 测试MySQL连接
  testConnection(configId) {
    return axios.post(`${baseURL}/${configId}/test`)
  }
}
