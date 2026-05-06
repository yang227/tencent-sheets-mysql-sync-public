import client from './client'

export const fetchWorkbenchSummary = () => client.get('/api/workbench/summary')
export const fetchCatalog = () => client.get('/api/workbench/catalog')
export const fetchDashboardHealth = () => client.get('/api/dashboard/health')
export const fetchDashboardOverview = () => client.get('/api/dashboard/overview')
