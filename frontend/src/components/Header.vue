<template>
  <div class="header">
    <div class="header-left">
      <el-icon class="collapse-btn" @click="toggleSidebar">
        <Fold v-if="!isCollapse" />
        <Expand v-else />
      </el-icon>
      <h1 class="header-title">MySQL同步管理系统</h1>
    </div>
    <div class="header-right">
      <el-badge :value="3" :hidden="false">
        <el-button :icon="Bell" circle />
      </el-badge>
      <el-dropdown trigger="click">
        <el-button class="user-btn">
          <el-icon><User /></el-icon>
          管理员
          <el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item>个人中心</el-dropdown-item>
            <el-dropdown-item>系统设置</el-dropdown-item>
            <el-dropdown-item divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Fold, Expand, Bell, User, ArrowDown } from '@element-plus/icons-vue'

const props = defineProps({
  isCollapse: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['toggle-sidebar'])

const toggleSidebar = () => {
  emit('toggle-sidebar')
}
</script>

<style scoped>
.header {
  height: 60px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 15px;
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
  transition: transform 0.3s;
}

.collapse-btn:hover {
  transform: scale(1.1);
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 15px;
}

.user-btn {
  background: rgba(255, 255, 255, 0.2;
  border: none;
  color: white;
}

.user-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}
</style>
