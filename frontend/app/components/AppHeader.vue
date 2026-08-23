<template>
  <header class="app-header">
    <div class="header-left">
      <el-icon class="collapse-btn" @click="appStore.toggleSidebar" :size="20">
        <Fold v-if="!appStore.sidebarCollapsed" />
        <Expand v-else />
      </el-icon>
    </div>

    <div class="header-right">
      <el-switch
        v-model="appStore.darkMode"
        @change="appStore.toggleDarkMode"
        :active-icon="Moon"
        :inactive-icon="Sunny"
        inline-prompt
        size="small"
      />
      <el-dropdown trigger="click">
        <div class="user-avatar">
          <el-avatar :size="32" :icon="UserFilled" />
          <span class="user-name">{{ authStore.user?.display_name || authStore.user?.email }}</span>
          <el-icon><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="$router.push('/profile')">
              <el-icon><User /></el-icon>个人资料
            </el-dropdown-item>
            <el-dropdown-item divided @click="handleLogout">
              <el-icon><SwitchButton /></el-icon>退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { useAuth } from '@/composables/useAuth'
import {
  Fold, Expand, Moon, Sunny, ArrowDown,
  User, SwitchButton, UserFilled,
} from '@element-plus/icons-vue'

const appStore = useAppStore()
const authStore = useAuthStore()
const { handleLogout } = useAuth()
</script>

<style lang="scss" scoped>
.app-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
  position: sticky;
  top: 0;
  z-index: 100;

  .header-left {
    .collapse-btn {
      cursor: pointer;
      color: var(--el-text-color-regular);
      &:hover { color: var(--el-color-primary); }
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 20px;

    .user-avatar {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      padding: 4px 8px;
      border-radius: 6px;
      transition: background 0.2s;

      &:hover {
        background: var(--el-fill-color-light);
      }

      .user-name {
        font-size: 14px;
        color: var(--el-text-color-regular);
        max-width: 120px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }
}
</style>
