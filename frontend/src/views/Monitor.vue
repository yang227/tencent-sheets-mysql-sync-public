<template>
  <div class="monitor">
    <el-row :gutter="20" class="stats-row">
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>实时状态</span>
              <el-button type="primary" link @click="refreshData">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </template>
          <div class="realtime-stats">
            <div class="stat-item">
              <span class="stat-label">运行中任务</span>
              <span class="stat-value success">{{ runningCount }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">等待中任务</span>
              <span class="stat-value warning">{{ waitingCount }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">今日同步次数</span>
              <span class="stat-value">{{ todayCount }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <span>任务执行日志</span>
          </template>
          <el-timeline>
            <el-timeline-item
              v-for="log in executionLogs"
              :key="log.id"
              :timestamp="log.time"
              :type="log.status === 'success' ? 'success' : log.status === 'error' ? 'danger' : 'warning'"
            >
              <div class="log-item">
                <strong>{{ log.taskName }}</strong>
                <p>{{ log.message }}</p>
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="chart-row">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <span>同步统计（最近7天）</span>
          </template>
          <div class="chart-placeholder">
            <p>图表组件待集成（可使用 ECharts 或 Chart.js）</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>任务监控列表</span>
            </div>
          </template>
          <el-table :data="monitorData" style="width: 100%">
            <el-table-column prop="taskName" label="任务名称" />
            <el-table-column prop="status" label="状态">
              <template #default="{ row }">
                <StatusBadge :status="row.status" />
              </template>
            </el-table-column>
            <el-table-column prop="lastSync" label="上次同步" />
            <el-table-column prop="nextSync" label="下次同步" />
            <el-table-column prop="recordsSynced" label="已同步记录" />
            <el-table-column prop="errorMsg" label="错误信息" />
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button type="primary" link @click="viewDetails(row)">
                  详情
                </el-button>
                <el-button type="warning" link @click="stopTask(row.id)">
                  停止
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import StatusBadge from '../components/StatusBadge.vue'
import syncApi from '../api/sync'

const runningCount = ref(0)
const waitingCount = ref(0)
const todayCount = ref(0)
const executionLogs = ref([])
const monitorData = ref([])
let refreshInterval = null

const refreshData = async () => {
  try {
    const data = await syncApi.getMonitorData()
    runningCount.value = data.runningCount
    waitingCount.value = data.waitingCount
    todayCount.value = data.todayCount
    executionLogs.value = data.logs
    monitorData.value = data.tasks
  } catch (error) {
    ElMessage.error('加载监控数据失败')
  }
}

const viewDetails = (row) => {
  ElMessage.info('查看详情功能开发中')
}

const stopTask = async (id) => {
  try {
    await syncApi.stopTask(id)
    ElMessage.success('任务已停止')
    refreshData()
  } catch (error) {
    ElMessage.error('停止任务失败')
  }
}

onMounted(() => {
  refreshData()
  // 每30秒自动刷新
  refreshInterval = setInterval(refreshData, 30000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.monitor {
  padding: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.chart-row {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.realtime-stats {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid #EBEEF5;
}

.stat-label {
  font-size: 14px;
  color: #606266;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.stat-value.success {
  color: #67C23A;
}

.stat-value.warning {
  color: #E6A23C;
}

.log-item p {
  margin: 5px 0 0 0;
  font-size: 12px;
  color: #909399;
}

.chart-placeholder {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #F5F7FA;
  border-radius: 4px;
  color: #909399;
}
</style>
