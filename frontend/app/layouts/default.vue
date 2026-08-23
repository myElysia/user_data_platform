<template>
  <div class="default-layout">
    <AppSidebar />
    <div class="layout-main" :class="{ collapsed: appStore.sidebarCollapsed }">
      <AppHeader />
      <div class="layout-content">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
</script>

<style lang="scss" scoped>
.default-layout {
  display: flex;
  min-height: 100vh;

  .layout-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    transition: margin-left 0.3s;

    .layout-content {
      flex: 1;
      padding: 20px;
      background: var(--el-bg-color-page);
      overflow-y: auto;
    }
  }
}
</style>
