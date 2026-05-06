<template>
  <span :class="['status-pill', toneClass]">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: 'default' },
  label: { type: String, default: '' },
})

const toneClass = computed(() => {
  const map = {
    success: 'is-success',
    healthy: 'is-success',
    running: 'is-info',
    partial: 'is-warning',
    warning: 'is-warning',
    failed: 'is-danger',
    critical: 'is-danger',
    degraded: 'is-warning',
    default: 'is-default',
  }
  return map[props.status] || 'is-default'
})
</script>

<style scoped>
.status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.is-success { background: #dcfce7; color: #166534; }
.is-info { background: #dbeafe; color: #1d4ed8; }
.is-warning { background: #fef3c7; color: #92400e; }
.is-danger { background: #fee2e2; color: #b91c1c; }
.is-default { background: #e2e8f0; color: #475569; }
</style>
