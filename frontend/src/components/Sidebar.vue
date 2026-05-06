<template>
  <div class="sidebar" :class="{ 'is-collapse': isCollapse }">
    <el-menu
      :default-active="activeMenu"
      :collapse="isCollapse"
      router
      background-color="#304156"
      text-color="#bfcbd9"
      active-text-color="#409EFF"
      class="sidebar-menu"
    >
      <el-menu-item index="/dashboard">
        <el-icon><Monitor /></el-icon>
        <template #title>仪表盘</template>
      </el-menu-item>

      <el-menu-item index="/mysql-config">
        <el-icon><Setting /></el-icon>
        <template #title>MySQL配置</template>
      </el-menu-item>

      <el-menu-item index="/tencent-config">
        <el-icon><Cloud /></el-icon>
        <template #title>腾讯云配置</template>
      </el-menu-item>

      <el-menu-item index="/sync-config">
        <el-icon><Refresh /></el-icon>
        <template #title>同步配置</template>
      </el-menu-item>

      <el-menu-item index="/monitor">
        <el-icon><DataAnalysis /></el-icon>
        <template #title>监控中心</template>
      </el-menu-item>
    </el-menu>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Monitor, Setting, Cloud, Refresh, DataAnalysis } from '@element-plus/icons-vue'

const props = defineProps({
  isCollapse: {
    type: Boolean,
    default: false
  }
})

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<style scoped>
.sidebar {
  height: 100%;
  transition: width 0.3s;
}

.sidebar-menu {
  height: 100%;
  border-right: none;
}

.sidebar-menu:not(.el-menu--collapse) {
  width: 210px;
}

.el-menu--collapse {
  width: 64px;
}

.el-menu-item {
  transition: all 0.3s;
}

.el-menu-item:hover {
  background-color: #263445 !important;
}
</style>
