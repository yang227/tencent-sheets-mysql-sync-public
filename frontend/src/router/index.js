import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: {
      title: '项目总览',
      description: '查看任务规模、最近同步结果与系统运行状态。',
    },
  },
  {
    path: '/connections',
    name: 'connections',
    component: () => import('../views/ConnectionsView.vue'),
    meta: {
      title: '连接中心',
      description: '统一管理 MySQL 与腾讯表格访问凭据。',
    },
  },
  {
    path: '/jobs',
    name: 'jobs',
    component: () => import('../views/SyncJobsView.vue'),
    meta: {
      title: '同步任务',
      description: '配置字段映射、同步方向与执行频率，并支持手动触发。',
    },
  },
  {
    path: '/monitor',
    name: 'monitor',
    component: () => import('../views/MonitorView.vue'),
    meta: {
      title: '运行监控',
      description: '聚合健康分、吞吐概览与错误面板，便于持续迭代优化。',
    },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = `${to.meta.title} - 腾讯表格同步平台`
})

export default router
