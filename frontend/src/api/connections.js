import client from './client'

export const listMysqlConfigs = () => client.get('/api/mysql-configs')
export const createMysqlConfig = (payload) => client.post('/api/mysql-configs', payload)
export const testMysqlConfig = (id) => client.post(`/api/mysql-configs/${id}/test`)

export const listTencentConfigs = () => client.get('/api/tencent-configs')
export const createTencentConfig = (payload) => client.post('/api/tencent-configs', payload)
export const testTencentConfig = (id) => client.post(`/api/tencent-configs/${id}/test`)
