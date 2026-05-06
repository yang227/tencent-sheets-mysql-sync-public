<template>
  <el-tag
    :type="statusType"
    :effect="effect"
    :size="size"
    class="status-badge"
  >
    <el-icon v-if="showIcon" class="status-icon">
      <component :is="statusIcon" />
    </el-icon>
    {{ statusText }}
  </el-tag>
</template>

<script setup>
import { computed } from 'vue'
import { CircleCheck, Warning, InfoFilled, Remove } from '@element-plus/icons-vue'

const props = defineProps({
  status: {
    type: String,
    required: true,
    validator: (value) => ['success', 'warning', 'error', 'info', 'disabled'].includes(value)
  },
  text: {
    type: String,
    default: ''
  },
  size: {
    type: String,
    default: 'default'
  },
  effect: {
    type: String,
    default: 'dark'
  },
  showIcon: {
    type: Boolean,
    default: true
  }
})

const statusConfig = {
  success: { type: 'success', icon: CircleCheck, text: '成功' },
  warning: { type: 'warning', icon: Warning, text: '警告' },
  error: { type: 'danger', icon: Warning, text: '错误' },
  info: { type: 'info', icon: InfoFilled, text: '运行中' },
  disabled: { type: 'info', icon: Remove, text: '已停止' }
}

const statusType = computed(() => statusConfig[props.status].type)
const statusIcon = computed(() => statusConfig[props.status].icon)
const statusText = computed(() => props.text || statusConfig[props.status].text)
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.status-icon {
  font-size: 12px;
}
</style>
