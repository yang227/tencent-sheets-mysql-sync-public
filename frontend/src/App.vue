<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">TS</div>
        <div>
          <div class="brand-title">腾讯表格同步平台</div>
          <div class="brand-subtitle">Tencent Sheets x MySQL</div>
        </div>
      </div>

      <nav class="nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-link"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </aside>

    <main class="main">
      <header class="topbar">
        <div>
          <h1>{{ route.meta.title }}</h1>
          <p>{{ route.meta.description }}</p>
        </div>
      </header>

      <section class="content">
        <RouterView />
      </section>
    </main>
  </div>
</template>

<script setup>
import { DataAnalysis, FolderOpened, Link, Refresh } from '@element-plus/icons-vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()

const navItems = [
  { path: '/', label: '总览', icon: DataAnalysis },
  { path: '/connections', label: '连接中心', icon: Link },
  { path: '/jobs', label: '同步任务', icon: Refresh },
  { path: '/monitor', label: '运行监控', icon: FolderOpened },
]
</script>
