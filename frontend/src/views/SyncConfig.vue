<template>
  <div class="sync-config">
    <el-row :gutter="20">
      <el-col :span="10">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>{{ isEditing ? '编辑同步任务' : '新增同步任务' }}</span>
            </div>
          </template>
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-width="120px"
          >
            <el-form-item label="任务名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入任务名称" />
            </el-form-item>

            <el-form-item label="MySQL配置" prop="mysql_config_id">
              <el-select v-model="form.mysql_config_id" placeholder="请选择MySQL配置">
                <el-option
                  v-for="item in mysqlConfigs"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="腾讯云配置" prop="tencent_config_id">
              <el-select v-model="form.tencent_config_id" placeholder="请选择腾讯云配置">
                <el-option
                  v-for="item in tencentConfigs"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="源数据表" prop="source_table">
              <el-input v-model="form.source_table" placeholder="请输入源数据表" />
            </el-form-item>

            <el-form-item label="目标文档" prop="target_document">
              <el-input v-model="form.target_document" placeholder="请输入目标文档ID" />
            </el-form-item>

            <el-form-item label="同步频率" prop="sync_interval">
              <el-select v-model="form.sync_interval" placeholder="请选择同步频率">
                <el-option label="每小时" :value="3600" />
                <el-option label="每6小时" :value="21600" />
                <el-option label="每12小时" :value="43200" />
                <el-option label="每天" :value="86400" />
                <el-option label="每周" :value="604800" />
              </el-select>
            </el-form-item>

            <el-form-item label="启用状态" prop="enabled">
              <el-switch v-model="form.enabled" />
            </el-form-item>

            <el-form-item>
              <el-button type="success" @click="saveTask" :loading="saving">
                {{ isEditing ? '更新' : '创建' }}
              </el-button>
              <el-button @click="resetForm" v-if="isEditing">取消编辑</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="14">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>任务列表</span>
              <el-button type="primary" size="small" @click="loadTasks">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </template>
          <el-table :data="tasks" style="width: 100%" v-loading="loading">
            <el-table-column prop="name" label="任务名称" />
            <el-table-column prop="source_table" label="源表" />
            <el-table-column prop="enabled" label="状态" width="100">
              <template #default="{ row }">
                <StatusBadge :status="row.enabled ? 'success' : 'disabled'" />
              </template>
            </el-table-column>
            <el-table-column prop="last_sync" label="上次同步" width="160" />
            <el-table-column label="操作" width="250">
              <template #default="{ row }">
                <el-button type="primary" link @click="editTask(row)">
                  编辑
                </el-button>
                <el-button
                  type="success"
                  link
                  @click="executeTask(row.id)"
                >
                  执行
                </el-button>
                <el-button
                  type="warning"
                  link
                  @click="toggleTask(row)"
                >
                  {{ row.enabled ? '停用' : '启用' }}
                </el-button>
                <el-button type="danger" link @click="deleteTask(row.id)">
                  删除
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import StatusBadge from '../components/StatusBadge.vue'
import syncApi from '../api/sync'
import mysqlApi from '../api/mysql'
import tencentApi from '../api/tencent'

const formRef = ref(null)
const isEditing = ref(false)
const editingId = ref(null)
const saving = ref(false)
const loading = ref(false)

const form = reactive({
  name: '',
  mysql_config_id: null,
  tencent_config_id: null,
  source_table: '',
  target_document: '',
  sync_interval: 86400,
  enabled: true
})

const rules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  mysql_config_id: [{ required: true, message: '请选择MySQL配置', trigger: 'change' }],
  tencent_config_id: [{ required: true, message: '请选择腾讯云配置', trigger: 'change' }],
  source_table: [{ required: true, message: '请输入源数据表', trigger: 'blur' }],
  target_document: [{ required: true, message: '请输入目标文档ID', trigger: 'blur' }]
}

const tasks = ref([])
const mysqlConfigs = ref([])
const tencentConfigs = ref([])

const loadTasks = async () => {
  loading.value = true
  try {
    const data = await syncApi.getTasks()
    tasks.value = data
  } catch (error) {
    ElMessage.error('加载任务失败')
  } finally {
    loading.value = false
  }
}

const loadConfigs = async () => {
  try {
    const [mysqlData, tencentData] = await Promise.all([
      mysqlApi.getConfigs(),
      tencentApi.getConfigs()
    ])
    mysqlConfigs.value = mysqlData
    tencentConfigs.value = tencentData
  } catch (error) {
    ElMessage.error('加载配置失败')
  }
}

const saveTask = async () => {
  await formRef.value.validate(async (valid) => {
    if (!valid) return

    saving.value = true
    try {
      if (isEditing.value) {
        await syncApi.updateTask(editingId.value, form)
        ElMessage.success('更新成功')
      } else {
        await syncApi.createTask(form)
        ElMessage.success('创建成功')
      }
      resetForm()
      loadTasks()
    } catch (error) {
      ElMessage.error('保存失败：' + error.message)
    } finally {
      saving.value = false
    }
  })
}

const editTask = (row) => {
  isEditing.value = true
  editingId.value = row.id
  Object.assign(form, row)
}

const executeTask = async (id) => {
  try {
    await ElMessageBox.confirm('确定执行该任务吗？', '提示', {
      type: 'info'
    })
    await syncApi.executeTask(id)
    ElMessage.success('任务已提交执行')
    loadTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('执行失败')
    }
  }
}

const toggleTask = async (row) => {
  try {
    const updated = { ...row, enabled: !row.enabled }
    await syncApi.updateTask(row.id, updated)
    ElMessage.success(row.enabled ? '已停用' : '已启用')
    loadTasks()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const deleteTask = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该任务吗？', '提示', {
      type: 'warning'
    })
    await syncApi.deleteTask(id)
    ElMessage.success('删除成功')
    loadTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const resetForm = () => {
  isEditing.value = false
  editingId.value = null
  formRef.value?.resetFields()
}

onMounted(() => {
  loadTasks()
  loadConfigs()
})
</script>

<style scoped>
.sync-config {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
