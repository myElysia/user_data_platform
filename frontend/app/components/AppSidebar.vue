<template>
  <el-menu
    :default-active="activeMenu"
    :collapse="appStore.sidebarCollapsed"
    :collapse-transition="false"
    class="app-sidebar"
    background-color="#001529"
    text-color="#ffffffb3"
    active-text-color="#fff"
  >
    <!-- Logo -->
    <div class="sidebar-logo">
      <el-icon :size="24" color="#409EFF"><Monitor /></el-icon>
      <span v-show="!appStore.sidebarCollapsed" class="logo-text">Zero Trust</span>
    </div>

    <!-- 用户菜单 -->
    <el-menu-item index="/" @click="$router.push('/')">
      <el-icon><HomeFilled /></el-icon>
      <template #title>仪表盘</template>
    </el-menu-item>
    <el-menu-item index="/profile" @click="$router.push('/profile')">
      <el-icon><User /></el-icon>
      <template #title>个人资料</template>
    </el-menu-item>
    <el-menu-item index="/oauth-apps" @click="$router.push('/oauth-apps')">
      <el-icon><Grid /></el-icon>
      <template #title>OAuth 应用</template>
    </el-menu-item>
    <el-menu-item index="/authorized-apps" @click="$router.push('/authorized-apps')">
      <el-icon><Check /></el-icon>
      <template #title>已授权应用</template>
    </el-menu-item>

    <!-- 管理员菜单 -->
    <template v-if="authStore.isAdmin">
      <el-divider style="margin: 8px 0; border-color: #ffffff22" />
      <div class="menu-group-title" v-show="!appStore.sidebarCollapsed">管理面板</div>
      <el-menu-item index="/admin" @click="$router.push('/admin')">
        <el-icon><DataAnalysis /></el-icon>
        <template #title>管理概览</template>
      </el-menu-item>
      <el-menu-item index="/admin/users" @click="$router.push('/admin/users')">
        <el-icon><Avatar /></el-icon>
        <template #title>用户管理</template>
      </el-menu-item>
      <el-menu-item index="/admin/clients" @click="$router.push('/admin/clients')">
        <el-icon><Connection /></el-icon>
        <template #title>客户端管理</template>
      </el-menu-item>
      <el-menu-item index="/admin/scopes" @click="$router.push('/admin/scopes')">
        <el-icon><Key /></el-icon>
        <template #title>Scope 管理</template>
      </el-menu-item>
      <el-menu-item index="/admin/webhooks" @click="$router.push('/admin/webhooks')">
        <el-icon><Bell /></el-icon>
        <template #title>Webhook 管理</template>
      </el-menu-item>
    </template>
  </el-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import {
  HomeFilled, User, Grid, Check, Monitor,
  DataAnalysis, Avatar, Connection, Key, Bell,
} from '@element-plus/icons-vue'

const route = useRoute()
const appStore = useAppStore()
const authStore = useAuthStore()

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/admin/users')) return '/admin/users'
  if (path.startsWith('/admin/clients')) return '/admin/clients'
  if (path.startsWith('/admin/scopes')) return '/admin/scopes'
  if (path.startsWith('/admin/webhooks')) return '/admin/webhooks'
  if (path.startsWith('/admin')) return '/admin'
  return path
})
</script>

<style lang="scss" scoped>
.app-sidebar {
  min-height: 100vh;
  border-right: none;
  user-select: none;

  .sidebar-logo {
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    overflow: hidden;

    .logo-text {
      font-size: 16px;
      font-weight: 700;
      color: #fff;
      white-space: nowrap;
    }
  }

  .menu-group-title {
    padding: 8px 20px;
    font-size: 12px;
    color: #ffffff55;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  .el-divider {
    margin: 4px 0;
  }

  &:not(.el-menu--collapse) {
    width: 220px;
  }
}
</style>
