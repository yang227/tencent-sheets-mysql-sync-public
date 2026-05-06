import client from './client'

export const listSyncJobs = () => client.get('/api/configs')
export const createSyncJob = (payload) => client.post('/api/configs', payload)
export const updateSyncJob = (id, payload) => client.put(`/api/configs/${id}`, payload)
export const deleteSyncJob = (id) => client.delete(`/api/configs/${id}`)
export const triggerSyncJob = (id) => client.post(`/api/sync/${id}/trigger`)

export const listDatabases = () => client.get('/api/mysql/databases')
export const listTables = (database) => client.get(`/api/mysql/databases/${database}/tables`)
export const listColumns = (tableName, database) =>
  client.get(`/api/mysql/tables/${tableName}/columns`, { params: { database } })

export const getSheetFields = (spreadsheetId, sheetName, headerRow = 1) =>
  client.get('/api/tencent/sheet-fields', {
    params: { spreadsheetId, sheetName, headerRow },
  })

export const autoMapFields = (spreadsheetId, sheetName, tableName, database, headerRow = 1) =>
  client.get('/api/tencent/auto-map', {
    params: { spreadsheetId, sheetName, tableName, database, headerRow },
  })
