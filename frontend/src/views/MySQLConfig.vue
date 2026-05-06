<template>
  <div class="mysql-config">
    <el-row :gutter="20">
      <el-col :span="10">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>{{ isEditing ? '编辑MySQL配置' : '新增MySQL配置' }}</span>
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

            <el-form-item label="主机地址" prop="host">
              <el-input v-model="form.host" placeholder="请输入主机地址" />
            </el-form-item>

            <el-form-item label="端口" prop="port">
              <el-input v-model.number="form.port" placeholder="请输入端口" type="number" />
            </el-form-item>

            <el-form-item label="用户名" prop="username">
              <el-input v-model="form.username" placeholder="请输入用户名" />
            </el-form-item>

            <el-form-item label="密码" prop="password">
              <el-input
                v-model="form.password"
                type="password"
                placeholder="请输入密码"
                show-password
              />
            </el-form-item>

            <el-form-item label="数据库名" prop="database_name">
              <el-input v-model="form.database_name" placeholder="请输入数据库名称" />
            </el-form-item>

            <el-form-item label="字符集" prop="charset">
              <el-input v-model="form.charset" placeholder="utf8mb4" />
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
            <el-table-column prop="host" label="主机" />
            <el-table-column prop="port" label="端口" width="80" />
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="database_name" label="数据库" />
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
import mysqlApi from '../api/mysql'

const formRef = ref(null)
const isEditing = ref(false)
const editingId = ref(null)
const testing = ref(false)
const saving = ref(false)
const loading = ref(false)

const form = reactive({
  name: '',
  host: '',
  port: 3306,
  username: '',
  password: '',
  database_name: '',
  charset: 'utf8mb4',
  description: '',
  is_active: true
})

const rules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  host: [{ required: true, message: '请输入主机地址', trigger: 'blur' }],
  port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  database_name: [{ required: true, message: '请输入数据库名称', trigger: 'blur' }]
}

const configs = ref([])

const loadConfigs = async () => {
  loading.value = true
  try {
    const response = await mysqlApi.getConfigs()
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
    // 测试连接使用表单数据
    const testData = { ...form }
    // 如果是编辑模式，使用已保存的配置ID测试
    if (isEditing.value && editingId.value) {
      await mysqlApi.testConnection(editingId.value)
    } else {
      // 新建配置，直接测试连接（不保存）
      ElMessage.info('请先保存配置后再测试连接')
      return
    }
    ElMessage.success('连接成功')
  } catch (error) {
    ElMessage.error('连接失败：' + (error.response?.data?.detail || error.message))
  } finally {
    testing.value = false
  }
}

const testConnectionById = async (id) => {
  testing.value = true
  try {
    await mysqlApi.testConnection(id)
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
      await mysqlApi.updateConfig(editingId.value, form)
      ElMessage.success('更新成功')
    } else {
      await mysqlApi.createConfig(form)
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
    host: row.host,
    port: row.port,
    username: row.username,
    password: '',  // 密码不回显
    database_name: row.database_name,
    charset: row.charset || 'utf8mb4',
    description: row.description || '',
    is_active: row.is_active
  })
}

const deleteConfig = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该配置吗？', '提示', {
      type: 'warning'
    })
    await mysqlApi.deleteConfig(id)
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
    host: '',
    port: 3306,
    username: '',
    password: '',
    database_name: '',
    charset: 'utf8mb4',
    description: '',
    is_active: true
  })
}

onMounted(() => {
  loadConfigs()
})
</script>

<style scoped>
.mysql-config {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
