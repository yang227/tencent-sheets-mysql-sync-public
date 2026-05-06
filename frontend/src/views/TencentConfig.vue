<template>
  <div class="tencent-config">
    <el-row :gutter="20">
      <el-col :span="10">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>{{ isEditing ? '编辑腾讯云配置' : '新增腾讯云配置' }}</span>
            </div>
          </template>
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-width="120px"
          >
            <el-form-item label="配置名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入配置名称" />
            </el-form-item>

            <el-form-item label="App ID" prop="app_id">
              <el-input v-model="form.app_id" placeholder="请输入App ID" />
            </el-form-item>

            <el-form-item label="Open ID" prop="open_id">
              <el-input v-model="form.open_id" placeholder="请输入Open ID" />
            </el-form-item>

            <el-form-item label="Access Token" prop="access_token">
              <el-input
                v-model="form.access_token"
                type="textarea"
                :rows="3"
                placeholder="请输入Access Token"
              />
            </el-form-item>

            <el-form-item label="Token过期时间" prop="token_expires_at">
              <el-date-picker
                v-model="form.token_expires_at"
                type="datetime"
                placeholder="选择过期时间（可选）"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item label="描述" prop="description">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="2"
                placeholder="配置描述（可选）"
              />
            </el-form-item>

            <el-form-item label="启用状态" prop="is_active">
              <el-switch v-model="form.is_active" />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="testConnection" :loading="testing">
                测试连接
              </el-button>
              <el-button type="success" @click="saveConfig" :loading="saving">
                {{ isEditing ? '更新' : '保存' }}
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
              <span>配置列表</span>
              <el-button type="primary" size="small" @click="loadConfigs">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </template>
          <el-table :data="configs" style="width: 100%" v-loading="loading">
            <el-table-column prop="name" label="配置名称" />
            <el-table-column prop="app_id" label="App ID" />
            <el-table-column prop="open_id" label="Open ID">
              <template #default="{ row }">
                {{ maskSecret(row.open_id) }}
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">
                  {{ row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button type="primary" link @click="editConfig(row)">
                  编辑
                </el-button>
                <el-button type="danger" link @click="deleteConfig(row.id)">
                  删除
                </el-button>
                <el-button type="success" link @click="testConnectionById(row.id)">
                  测试
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
import tencentApi from '../api/tencent'

const formRef = ref(null)
const isEditing = ref(false)
const editingId = ref(null)
const testing = ref(false)
const saving = ref(false)
const loading = ref(false)

const form = reactive({
  name: '',
  app_id: '',
  open_id: '',
  access_token: '',
  token_expires_at: null,
  description: '',
  is_active: true
})

const rules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  app_id: [{ required: true, message: '请输入App ID', trigger: 'blur' }],
  open_id: [{ required: true, message: '请输入Open ID', trigger: 'blur' }],
  access_token: [{ required: true, message: '请输入Access Token', trigger: 'blur' }]
}

const configs = ref([])

const maskSecret = (secret) => {
  if (!secret) return ''
  if (secret.length <= 8) return '****'
  return secret.substring(0, 4) + '****' + secret.substring(secret.length - 4)
}

const loadConfigs = async () => {
  loading.value = true
  try {
    const response = await tencentApi.getConfigs()
    configs.value = response.data
  } catch (error) {
    ElMessage.error('加载配置失败：' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

const testConnection = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
  } catch (e) {
    return
  }
  
  testing.value = true
  try {
    if (isEditing.value && editingId.value) {
      await tencentApi.testConnection(editingId.value)
      ElMessage.success('连接成功')
    } else {
      ElMessage.info('请先保存配置后再测试连接')
    }
  } catch (error) {
    ElMessage.error('连接失败：' + (error.response?.data?.detail || error.message))
  } finally {
    testing.value = false
  }
}

const testConnectionById = async (id) => {
  testing.value = true
  try {
    await tencentApi.testConnection(id)
    ElMessage.success('连接成功')
  } catch (error) {
    ElMessage.error('连接失败：' + (error.response?.data?.detail || error.message))
  } finally {
    testing.value = false
  }
}

const saveConfig = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
  } catch (e) {
    return
  }
  
  saving.value = true
  try {
    if (isEditing.value) {
      await tencentApi.updateConfig(editingId.value, form)
      ElMessage.success('更新成功')
    } else {
      await tencentApi.createConfig(form)
      ElMessage.success('保存成功')
    }
    resetForm()
    loadConfigs()
  } catch (error) {
    ElMessage.error('保存失败：' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

const editConfig = (row) => {
  isEditing.value = true
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    app_id: row.app_id,
    open_id: row.open_id,
    access_token: '',  // Token不回显
    token_expires_at: row.token_expires_at ? new Date(row.token_expires_at) : null,
    description: row.description || '',
    is_active: row.is_active
  })
}

const deleteConfig = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该配置吗？', '提示', {
      type: 'warning'
    })
    await tencentApi.deleteConfig(id)
    ElMessage.success('删除成功')
    loadConfigs()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败：' + (error.response?.data?.detail || error.message))
    }
  }
}

const resetForm = () => {
  isEditing.value = false
  editingId.value = null
  formRef.value?.resetFields()
  Object.assign(form, {
    name: '',
    app_id: '',
    open_id: '',
    access_token: '',
    token_expires_at: null,
    description: '',
    is_active: true
  })
}

onMounted(() => {
  loadConfigs()
})
</script>

<style scoped>
.tencent-config {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
