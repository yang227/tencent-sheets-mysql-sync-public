<template>
  <div class="panel">
    <div class="muted">{{ label }}</div>
    <div style="display:flex;align-items:flex-end;justify-content:space-between;margin-top:10px;">
      <div style="font-size:30px;font-weight:700;">{{ value }}</div>
      <div class="muted">{{ hint }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], required: true },
  hint: { type: String, default: '' },
})
</script>
