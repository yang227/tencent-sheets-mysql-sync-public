<template>
  <div class="page-grid">
    <el-alert
      title="同步任务创建前提"
      type="info"
      :closable="false"
      show-icon
      description="先确认腾讯表格可访问，再选定目标 MySQL 表，即可直接读取字段并自动生成映射。"
    />

    <div class="split-grid">
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">{{ editingId ? '编辑同步任务' : '新建同步任务' }}</div>
          <el-button @click="resetForm">清空</el-button>
        </div>

        <el-form :model="form" label-width="110px">
          <el-form-item label="Spreadsheet ID">
            <el-input v-model="form.spreadsheet_id" />
          </el-form-item>
          <el-form-item label="Sheet ID">
            <el-input v-model="form.sheet_id" />
          </el-form-item>
          <el-form-item label="表头行">
            <el-input-number v-model="form.mapping_json.sheet_header_row" :min="1" :max="50" />
          </el-form-item>
          <el-form-item label="目标数据库">
            <el-select v-model="form.database" filterable @change="loadTablesForDatabase">
              <el-option
                v-for="item in databases"
                :key="item.name"
                :label="item.label"
                :value="item.name"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="目标表">
            <el-select v-model="form.table_name" filterable @change="loadMysqlColumns">
              <el-option
                v-for="item in tables"
                :key="item.name"
                :label="item.label"
                :value="item.name"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="同步方向">
            <el-select v-model="form.sync_direction">
              <el-option v-for="item in directions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="轮询秒数">
            <el-input-number v-model="form.poll_interval" :min="10" :max="86400" />
          </el-form-item>

          <div class="panel" style="padding: 14px; margin-top: 8px;">
            <div class="panel-header" style="margin-bottom: 12px;">
              <div class="panel-title">字段映射</div>
              <div style="display:flex; gap:8px; flex-wrap:wrap;">
                <el-button size="small" @click="loadSheetFields">读取腾讯字段</el-button>
                <el-button size="small" @click="loadMysqlColumns">读取 MySQL 字段</el-button>
                <el-button size="small" type="primary" @click="applyAutoMapping">一键自动映射</el-button>
                <el-button size="small" link @click="appendMapping">新增一行</el-button>
              </div>
            </div>

            <el-alert
              v-if="mappingHint"
              :title="mappingHint"
              type="warning"
              :closable="false"
              show-icon
              style="margin-bottom: 12px;"
            />

            <div class="mapping-grid">
              <div
                v-for="(row, index) in form.mapping_json.columns"
                :key="index"
                class="mapping-row"
              >
                <el-select v-model="row.sheet_col" filterable placeholder="列号" @change="syncSheetHeader(row)">
                  <el-option
                    v-for="field in sheetFields"
                    :key="field.sheet_col"
                    :label="field.display_name"
                    :value="field.sheet_col"
                  />
                </el-select>
                <el-input v-model="row.sheet_header" placeholder="表头名" />
                <el-select v-model="row.db_column" filterable placeholder="MySQL 字段" @change="syncMysqlType(row)">
                  <el-option
                    v-for="field in mysqlFields"
                    :key="field.name"
                    :label="`${field.name} (${field.type})`"
                    :value="field.name"
                  />
                </el-select>
                <el-input v-model="row.db_type" placeholder="字段类型" />
                <el-select v-model="row.direction">
                  <el-option
                    v-for="item in columnDirections"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
                <el-checkbox v-model="row.primary_key">主键</el-checkbox>
                <el-button link type="danger" @click="removeMapping(index)">删</el-button>
              </div>
            </div>
          </div>

          <div style="margin-top: 16px;">
            <el-button type="primary" @click="submitJob">{{ editingId ? '更新任务' : '创建任务' }}</el-button>
          </div>
        </el-form>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">字段预览</div>
        </div>

        <div class="split-grid" style="grid-template-columns: minmax(0,1fr) minmax(0,1fr); gap:16px;">
          <div>
            <div class="table-toolbar">
              <strong>腾讯表格字段</strong>
              <span class="muted">{{ sheetFields.length }} 列</span>
            </div>
            <el-table :data="sheetFields" height="260" empty-text="先读取腾讯字段">
              <el-table-column prop="sheet_col" label="列" width="72" />
              <el-table-column prop="sheet_header" label="表头" min-width="150" />
            </el-table>
          </div>

          <div>
            <div class="table-toolbar">
              <strong>MySQL 字段</strong>
              <span class="muted">{{ mysqlFields.length }} 列</span>
            </div>
            <el-table :data="mysqlFields" height="260" empty-text="先读取 MySQL 字段">
              <el-table-column prop="name" label="字段" min-width="150" />
              <el-table-column prop="type" label="类型" width="120" />
              <el-table-column label="主键" width="72">
                <template #default="{ row }">{{ row.primary_key ? '是' : '否' }}</template>
              </el-table-column>
            </el-table>
          </div>
        </div>

        <div class="panel-header" style="margin-top: 20px;">
          <div class="panel-title">现有同步任务</div>
          <el-button @click="loadJobs">刷新</el-button>
        </div>
        <el-table :data="jobs" empty-text="暂无同步任务">
          <el-table-column prop="table_name" label="表名" min-width="140" />
          <el-table-column prop="sheet_id" label="Sheet ID" min-width="150" />
          <el-table-column prop="sync_direction" label="方向" width="130" />
          <el-table-column prop="poll_interval" label="轮询" width="90" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <StatusPill :status="row.is_active ? 'success' : 'default'" :label="row.is_active ? 'active' : 'inactive'" />
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="220">
            <template #default="{ row }">
              <el-button link type="primary" @click="editJob(row)">编辑</el-button>
              <el-button link type="success" @click="runJob(row.id)">执行</el-button>
              <el-button link type="danger" @click="removeJob(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import StatusPill from '../components/StatusPill.vue'
import { fetchCatalog } from '../api/workbench'
import {
  autoMapFields,
  createSyncJob,
  deleteSyncJob,
  getSheetFields,
  listColumns,
  listDatabases,
  listSyncJobs,
  listTables,
  triggerSyncJob,
  updateSyncJob,
} from '../api/sync-jobs'

const jobs = ref([])
const databases = ref([])
const tables = ref([])
const mysqlFields = ref([])
const sheetFields = ref([])
const directions = ref([])
const columnDirections = ref([])
const editingId = ref(null)
const mappingHint = ref('')

const emptyMappingRow = () => ({
  sheet_col: '',
  sheet_header: '',
  db_column: '',
  db_type: '',
  direction: 'bidirectional',
  primary_key: false,
  transform: null,
})

const defaultForm = () => ({
  spreadsheet_id: '',
  sheet_id: '',
  table_name: '',
  database: '',
  sync_direction: 'bidirectional',
  poll_interval: 30,
  mapping_json: {
    sheet_header_row: 1,
    data_start_row: 2,
    columns: [emptyMappingRow()],
  },
})

const form = ref(defaultForm())

const resetForm = () => {
  editingId.value = null
  form.value = defaultForm()
  mysqlFields.value = []
  sheetFields.value = []
  mappingHint.value = ''
}

const appendMapping = () => {
  form.value.mapping_json.columns.push(emptyMappingRow())
}

const removeMapping = (index) => {
  form.value.mapping_json.columns.splice(index, 1)
  if (form.value.mapping_json.columns.length === 0) {
    appendMapping()
  }
}

const findSheetField = (sheetCol) => sheetFields.value.find((item) => item.sheet_col === sheetCol)
const findMysqlField = (dbColumn) => mysqlFields.value.find((item) => item.name === dbColumn)

const syncSheetHeader = (row) => {
  const match = findSheetField(row.sheet_col)
  if (match) {
    row.sheet_header = match.sheet_header
  }
}

const syncMysqlType = (row) => {
  const match = findMysqlField(row.db_column)
  if (match) {
    row.db_type = match.type
    row.primary_key = !!match.primary_key
  }
}

const loadCatalog = async () => {
  const [catalog, mysqlDatabases] = await Promise.all([
    fetchCatalog(),
    listDatabases(),
  ])
  directions.value = catalog.directions
  columnDirections.value = catalog.column_directions
  databases.value = mysqlDatabases
}

const loadJobs = async () => {
  jobs.value = await listSyncJobs()
}

const loadTablesForDatabase = async (database) => {
  if (!database) return
  tables.value = await listTables(database)
}

const loadMysqlColumns = async () => {
  if (!form.value.table_name || !form.value.database) {
    ElMessage.warning('请先选择目标数据库和目标表')
    return
  }
  mysqlFields.value = await listColumns(form.value.table_name, form.value.database)
}

const loadSheetFields = async () => {
  if (!form.value.spreadsheet_id || !form.value.sheet_id) {
    ElMessage.warning('请先填写 Spreadsheet ID 和 Sheet ID')
    return
  }
  const result = await getSheetFields(
    form.value.spreadsheet_id,
    form.value.sheet_id,
    form.value.mapping_json.sheet_header_row,
  )
  sheetFields.value = result.fields || []
  mappingHint.value = result.demo
    ? '当前返回的是演示字段，请检查腾讯凭据或表格权限后再正式建模。'
    : result.warning || ''
}

const applyAutoMapping = async () => {
  if (!form.value.spreadsheet_id || !form.value.sheet_id || !form.value.table_name || !form.value.database) {
    ElMessage.warning('请先填写腾讯表格信息并选择 MySQL 目标表')
    return
  }

  const result = await autoMapFields(
    form.value.spreadsheet_id,
    form.value.sheet_id,
    form.value.table_name,
    form.value.database,
    form.value.mapping_json.sheet_header_row,
  )

  sheetFields.value = result.sheet_fields || []
  mysqlFields.value = result.mysql_fields || []
  form.value.mapping_json.columns =
    (result.suggested_mappings || []).length > 0
      ? result.suggested_mappings.map((item) => ({
          sheet_col: item.sheet_col,
          sheet_header: item.sheet_header,
          db_column: item.db_column,
          db_type: item.db_type,
          direction: item.direction,
          primary_key: item.primary_key,
          transform: item.transform,
        }))
      : [emptyMappingRow()]

  if (result.warnings?.length) {
    mappingHint.value = result.warnings.join(' | ')
  } else {
    mappingHint.value = result.suggested_mappings?.length
      ? `已自动生成 ${result.suggested_mappings.length} 条映射`
      : '未找到可自动匹配的字段，请手动调整'
  }
}

const submitJob = async () => {
  try {
    if (editingId.value) {
      await updateSyncJob(editingId.value, form.value)
      ElMessage.success('同步任务已更新')
    } else {
      await createSyncJob(form.value)
      ElMessage.success('同步任务已创建')
    }
    resetForm()
    await loadJobs()
  } catch (error) {
    ElMessage.error(error.message)
  }
}

const editJob = async (row) => {
  editingId.value = row.id
  form.value = JSON.parse(JSON.stringify(row))
  mappingHint.value = ''
  if (row.database) {
    await loadTablesForDatabase(row.database)
  }
  if (row.table_name && row.database) {
    await loadMysqlColumns()
  }
  if (row.spreadsheet_id && row.sheet_id) {
    await loadSheetFields()
  }
}

const runJob = async (id) => {
  try {
    const result = await triggerSyncJob(id)
    ElMessage.success(result.message || '同步已触发')
    await loadJobs()
  } catch (error) {
    ElMessage.error(error.message)
  }
}

const removeJob = async (id) => {
  try {
    await deleteSyncJob(id)
    ElMessage.success('同步任务已删除')
    await loadJobs()
  } catch (error) {
    ElMessage.error(error.message)
  }
}

const boot = async () => {
  try {
    await loadCatalog()
    await loadJobs()
  } catch (error) {
    ElMessage.error(error.message)
  }
}

onMounted(boot)
</script>
