<template>
  <div class="page-grid">
    <el-alert
      v-if="summary.mysql_connection && summary.mysql_connection.connected === false"
      title="平台元数据库未连接，系统当前处于初始化只读模式"
      type="warning"
      :closable="false"
      show-icon
      :description="summary.mysql_connection.error || '请检查 config.yaml 中的 database 配置。'"
    />

    <div class="metrics-grid">
      <MetricCard label="同步任务" :value="summary.counts.sync_configs" hint="激活配置数" />
      <MetricCard label="MySQL 连接" :value="summary.counts.mysql_configs" hint="可用凭据" />
      <MetricCard label="腾讯配置" :value="summary.counts.tencent_configs" hint="API 凭据数" />
      <MetricCard label="累计执行" :value="summary.counts.sync_runs" hint="同步运行次数" />
    </div>

    <div class="split-grid">
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">最近执行</div>
          <el-button @click="loadAll">刷新</el-button>
        </div>
        <el-table :data="summary.recent_runs" empty-text="暂无同步记录">
          <el-table-column prop="table_name" label="目标表" min-width="160" />
          <el-table-column prop="direction" label="方向" width="130" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <StatusPill :status="row.status" :label="row.status" />
            </template>
          </el-table-column>
          <el-table-column prop="rows_affected" label="影响行数" width="110" />
          <el-table-column prop="started_at" label="开始时间" min-width="180" />
        </el-table>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">系统健康</div>
          <StatusPill :status="health.status" :label="health.status || 'unknown'" />
        </div>
        <div class="status-stack">
          <div class="status-row">
            <span>健康分</span>
            <strong>{{ health.health_score ?? '-' }}</strong>
          </div>
          <div class="status-row">
            <span>MySQL 连接</span>
            <StatusPill
              :status="summary.mysql_connection.connected ? 'success' : 'failed'"
              :label="summary.mysql_connection.connected ? 'connected' : 'failed'"
            />
          </div>
          <div class="status-row">
            <span>成功运行</span>
            <strong>{{ summary.counts.success_runs }}</strong>
          </div>
          <div class="status-row">
            <span>失败运行</span>
            <strong>{{ summary.counts.failed_runs }}</strong>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'

import MetricCard from '../components/MetricCard.vue'
import StatusPill from '../components/StatusPill.vue'
import { fetchDashboardHealth, fetchWorkbenchSummary } from '../api/workbench'

const summary = reactive({
  counts: {
    sync_configs: 0,
    mysql_configs: 0,
    tencent_configs: 0,
    sync_runs: 0,
    success_runs: 0,
    failed_runs: 0,
  },
  mysql_connection: {},
  recent_runs: [],
})

const health = reactive({})

const loadAll = async () => {
  try {
    const [summaryData, healthData] = await Promise.all([
      fetchWorkbenchSummary(),
      fetchDashboardHealth(),
    ])
    Object.assign(summary, summaryData)
    Object.assign(health, healthData)
  } catch (error) {
    ElMessage.error(error.message)
  }
}

onMounted(loadAll)
</script>
