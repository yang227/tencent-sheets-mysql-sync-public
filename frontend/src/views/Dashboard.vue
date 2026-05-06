<template>
  <div class="dashboard">
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card class="stats-card" shadow="hover">
          <div class="stats-content">
            <el-icon class="stats-icon" color="#409EFF"><SetUp /></el-icon>
            <div class="stats-info">
              <div class="stats-value">{{ stats.taskCount }}</div>
              <div class="stats-label">同步任务</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stats-card" shadow="hover">
          <div class="stats-content">
            <el-icon class="stats-icon" color="#67C23A"><CircleCheck /></el-icon>
            <div class="stats-info">
              <div class="stats-value">{{ stats.successCount }}</div>
              <div class="stats-label">成功执行</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stats-card" shadow="hover">
          <div class="stats-content">
            <el-icon class="stats-icon" color="#E6A23C"><Warning /></el-icon>
            <div class="stats-info">
              <div class="stats-value">{{ stats.warningCount }}</div>
              <div class="stats-label">警告</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stats-card" shadow="hover">
          <div class="stats-content">
            <el-icon class="stats-icon" color="#F56C6C"><CircleClose /></el-icon>
            <div class="stats-info">
              <div class="stats-value">{{ stats.errorCount }}</div>
              <div class="stats-label">失败</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="content-row">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>快速入口</span>
            </div>
          </template>
          <el-row :gutter="15">
            <el-col :span="8">
              <div class="quick-access-item" @click="$router.push('/mysql-config')">
                <el-icon :size="32" color="#409EFF"><Setting /></el-icon>
                <span>MySQL配置</span>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="quick-access-item" @click="$router.push('/tencent-config')">
                <el-icon :size="32" color="#67C23A"><Cloud /></el-icon>
                <span>腾讯云配置</span>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="quick-access-item" @click="$router.push('/sync-config')">
                <el-icon :size="32" color="#E6A23C"><Refresh /></el-icon>
                <span>同步配置</span>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="quick-access-item" @click="$router.push('/monitor')">
                <el-icon :size="32" color="#F56C6C"><DataAnalysis /></el-icon>
                <span>监控中心</span>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>最近任务</span>
              <el-button type="primary" link @click="$router.push('/sync-config')">
                查看全部
              </el-button>
            </div>
          </template>
          <el-timeline>
            <el-timeline-item
              v-for="task in recentTasks"
              :key="task.id"
              :timestamp="task.time"
              placement="top"
            >
              <div class="task-item">
                <span class="task-name">{{ task.name }}</span>
                <StatusBadge :status="task.status" :size="'small'" />
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="content-row">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>系统状态</span>
            </div>
          </template>
          <el-table :data="systemStatus" style="width: 100%">
            <el-table-column prop="service" label="服务" />
            <el-table-column prop="status" label="状态">
              <template #default="{ row }">
                <StatusBadge :status="row.status" :text="row.statusText" />
              </template>
            </el-table-column>
            <el-table-column prop="message" label="信息" />
            <el-table-column prop="updateTime" label="更新时间" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { SetUp, CircleCheck, Warning, CircleClose, Setting, Cloud, Refresh, DataAnalysis } from '@element-plus/icons-vue'
import StatusBadge from '../components/StatusBadge.vue'
import syncApi from '../api/sync'

const stats = ref({
  taskCount: 0,
  successCount: 0,
  warningCount: 0,
  errorCount: 0
})

const recentTasks = ref([
  { id: 1, name: '用户数据同步', status: 'success', time: '2024-01-15 10:30:00' },
  { id: 2, name: '订单数据同步', status: 'warning', time: '2024-01-15 09:15:00' },
  { id: 3, name: '产品数据同步', status: 'info', time: '2024-01-15 08:00:00' }
])

const systemStatus = ref([
  { service: 'MySQL连接', status: 'success', statusText: '正常', message: '连接池：10/50', updateTime: '2024-01-15 10:30:00' },
  { service: '腾讯云API', status: 'success', statusText: '正常', message: '速率限制：100/1000', updateTime: '2024-01-15 10:30:00' },
  { service: '同步引擎', status: 'info', statusText: '运行中', message: '当前任务：2', updateTime: '2024-01-15 10:30:00' }
])

onMounted(async () => {
  try {
    const data = await syncApi.getDashboard()
    stats.value = data.stats
    recentTasks.value = data.recentTasks
    systemStatus.value = data.systemStatus
  } catch (error) {
    console.error('Failed to load dashboard data:', error)
  }
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stats-card {
  cursor: pointer;
  transition: transform 0.3s;
}

.stats-card:hover {
  transform: translateY(-5px);
}

.stats-content {
  display: flex;
  align-items: center;
  gap: 15px;
}

.stats-icon {
  font-size: 48px;
}

.stats-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stats-label {
  font-size: 14px;
  color: #909399;
}

.content-row {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.quick-access-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 20px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  border: 1px solid #DCDFE6;
}

.quick-access-item:hover {
  background-color: #ECF5FF;
  border-color: #409EFF;
}

.task-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
