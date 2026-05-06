import axios from 'axios'

const baseURL = '/api/tencent-configs'

export default {
  // 获取所有腾讯云配置
  getConfigs() {
    return axios.get(`${baseURL}`)
  },

  // 获取单个腾讯云配置
  getConfig(id) {
    return axios.get(`${baseURL}/${id}`)
  },

  // 创建腾讯云配置
  createConfig(data) {
    return axios.post(`${baseURL}`, data)
  },

  // 更新腾讯云配置
  updateConfig(id, data) {
    return axios.put(`${baseURL}/${id}`, data)
  },

  // 删除腾讯云配置
  deleteConfig(id) {
    return axios.delete(`${baseURL}/${id}`)
  },

  // 测试腾讯云API连接
  testConnection(configId) {
    return axios.post(`${baseURL}/${configId}/test`)
  }
}
