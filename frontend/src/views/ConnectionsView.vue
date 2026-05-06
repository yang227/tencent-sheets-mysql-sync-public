<template>
  <div class="page-grid">
    <el-alert
      title="连接中心依赖平台元数据库"
      type="info"
      :closable="false"
      show-icon
      description="如果列表为空且无法保存，请先确认后端 config.yaml 中的平台数据库已可连接，再通过本页维护业务连接。"
    />

    <div class="split-grid">
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">MySQL 连接配置</div>
          <el-button type="primary" @click="createMysql">新增 MySQL</el-button>
        </div>
        <el-table :data="mysqlConfigs" empty-text="暂无配置">
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column prop="host" label="主机" min-width="150" />
          <el-table-column prop="database_name" label="数据库" min-width="140" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <StatusPill :status="row.test_status" :label="row.test_status" />
            </template>
          </el-table-column>
          <el-table-column width="120" label="操作">
            <template #default="{ row }">
              <el-button link type="primary" @click="runMysqlTest(row.id)">测试</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">腾讯 API 配置</div>
          <el-button type="primary" @click="createTencent">新增腾讯配置</el-button>
        </div>
        <el-table :data="tencentConfigs" empty-text="暂无配置">
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column prop="app_id" label="App ID" min-width="170" />
          <el-table-column prop="open_id" label="Open ID" min-width="170" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <StatusPill :status="row.test_status" :label="row.test_status" />
            </template>
          </el-table-column>
          <el-table-column width="120" label="操作">
            <template #default="{ row }">
              <el-button link type="primary" @click="runTencentTest(row.id)">测试</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <el-dialog v-model="mysqlDialogVisible" title="新增 MySQL 连接" width="560px">
      <el-form :model="mysqlForm" label-width="100px">
        <el-form-item label="名称"><el-input v-model="mysqlForm.name" /></el-form-item>
        <el-form-item label="主机"><el-input v-model="mysqlForm.host" /></el-form-item>
        <el-form-item label="端口"><el-input-number v-model="mysqlForm.port" :min="1" :max="65535" /></el-form-item>
        <el-form-item label="用户名"><el-input v-model="mysqlForm.username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="mysqlForm.password" show-password /></el-form-item>
        <el-form-item label="数据库"><el-input v-model="mysqlForm.database_name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="mysqlForm.description" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mysqlDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveMysql">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="tencentDialogVisible" title="新增腾讯配置" width="560px">
      <el-form :model="tencentForm" label-width="100px">
        <el-form-item label="名称"><el-input v-model="tencentForm.name" /></el-form-item>
        <el-form-item label="App ID"><el-input v-model="tencentForm.app_id" /></el-form-item>
        <el-form-item label="Open ID"><el-input v-model="tencentForm.open_id" /></el-form-item>
        <el-form-item label="Access Token"><el-input v-model="tencentForm.access_token" type="textarea" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="tencentForm.description" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="tencentDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTencent">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import StatusPill from '../components/StatusPill.vue'
import {
  createMysqlConfig,
  createTencentConfig,
  listMysqlConfigs,
  listTencentConfigs,
  testMysqlConfig,
  testTencentConfig,
} from '../api/connections'

const mysqlConfigs = ref([])
const tencentConfigs = ref([])

const mysqlDialogVisible = ref(false)
const tencentDialogVisible = ref(false)

const mysqlForm = ref({
  name: '',
  host: '127.0.0.1',
  port: 3306,
  username: 'root',
  password: '',
  database_name: '',
  charset: 'utf8mb4',
  description: '',
  is_active: true,
})

const tencentForm = ref({
  name: '',
  app_id: '',
  open_id: '',
  access_token: '',
  description: '',
  is_active: true,
  token_expires_at: null,
})

const resetMysql = () => {
  mysqlForm.value = {
    name: '',
    host: '127.0.0.1',
    port: 3306,
    username: 'root',
    password: '',
    database_name: '',
    charset: 'utf8mb4',
    description: '',
    is_active: true,
  }
}

const resetTencent = () => {
  tencentForm.value = {
    name: '',
    app_id: '',
    open_id: '',
    access_token: '',
    description: '',
    is_active: true,
    token_expires_at: null,
  }
}

const loadData = async () => {
  try {
    const [mysqlData, tencentData] = await Promise.all([
      listMysqlConfigs(),
      listTencentConfigs(),
    ])
    mysqlConfigs.value = mysqlData
    tencentConfigs.value = tencentData
  } catch (error) {
    ElMessage.error(error.message)
  }
}

const createMysql = () => {
  resetMysql()
  mysqlDialogVisible.value = true
}

const createTencent = () => {
  resetTencent()
  tencentDialogVisible.value = true
}

const saveMysql = async () => {
  try {
    await createMysqlConfig(mysqlForm.value)
    mysqlDialogVisible.value = false
    ElMessage.success('MySQL 配置已创建')
    await loadData()
  } catch (error) {
    ElMessage.error(error.message)
  }
}

const saveTencent = async () => {
  try {
    await createTencentConfig(tencentForm.value)
    tencentDialogVisible.value = false
    ElMessage.success('腾讯配置已创建')
    await loadData()
  } catch (error) {
    ElMessage.error(error.message)
  }
}

const runMysqlTest = async (id) => {
  try {
    const result = await testMysqlConfig(id)
    ElMessage.success(result.message)
    await loadData()
  } catch (error) {
    ElMessage.error(error.message)
  }
}

const runTencentTest = async (id) => {
  try {
    const result = await testTencentConfig(id)
    ElMessage.success(result.message)
    await loadData()
  } catch (error) {
    ElMessage.error(error.message)
  }
}

onMounted(loadData)
</script>
