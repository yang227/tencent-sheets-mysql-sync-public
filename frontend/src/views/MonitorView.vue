<template>
  <div class="page-grid">
    <div class="metrics-grid">
      <MetricCard label="总同步次数" :value="overview.sync_overview.total_syncs || 0" hint="平台累计" />
      <MetricCard label="成功率" :value="`${overview.sync_overview.success_rate || 0}%`" hint="按采集指标" />
      <MetricCard label="API 调用" :value="overview.api_overview.total_calls || 0" hint="外部接口请求" />
      <MetricCard label="错误总数" :value="overview.error_overview.total_errors || 0" hint="含可重试错误" />
    </div>

    <div class="split-grid">
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">系统健康面板</div>
          <StatusPill :status="health.status" :label="health.status || 'unknown'" />
        </div>
        <div class="status-stack">
          <div v-for="(check, key) in health.checks || {}" :key="key" class="status-row">
            <span>{{ key }}</span>
            <div style="display:flex;gap:12px;align-items:center;">
              <strong>{{ check.value }}</strong>
              <StatusPill :status="check.status" :label="check.status" />
            </div>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">吞吐与审计</div>
        </div>
        <div class="status-stack">
          <div class="status-row">
            <span>同步行数</span>
            <strong>{{ overview.sync_overview.rows_synced || 0 }}</strong>
          </div>
          <div class="status-row">
            <span>平均耗时</span>
            <strong>{{ overview.sync_overview.avg_duration || 0 }}</strong>
          </div>
          <div class="status-row">
            <span>审计事件</span>
            <strong>{{ overview.audit_overview.total_events || 0 }}</strong>
          </div>
          <div class="status-row">
            <span>死信队列</span>
            <strong>{{ overview.dead_letter_queue.total_items || 0 }}</strong>
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
import { fetchDashboardHealth, fetchDashboardOverview } from '../api/workbench'

const overview = reactive({
  sync_overview: {},
  api_overview: {},
  audit_overview: {},
  error_overview: {},
  dead_letter_queue: {},
})

const health = reactive({})

const loadAll = async () => {
  try {
    const [overviewData, healthData] = await Promise.all([
      fetchDashboardOverview(),
      fetchDashboardHealth(),
    ])
    Object.assign(overview, overviewData)
    Object.assign(health, healthData)
  } catch (error) {
    ElMessage.error(error.message)
  }
}

onMounted(loadAll)
</script>
