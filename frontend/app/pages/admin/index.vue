<template>
  <div class="admin-dashboard">
    <h1 class="page-title">管理概览</h1>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="6" v-for="item in stats" :key="item.label">
        <el-card shadow="hover" class="stat-card" @click="$router.push(item.link)">
          <div class="stat-icon" :style="{ background: item.bg }">
            <el-icon :size="28" :color="item.color"><component :is="item.icon" /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ item.value }}</div>
            <div class="stat-label">{{ item.label }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>管理快捷操作</span>
        </div>
      </template>
      <el-space wrap>
        <el-button type="primary" @click="$router.push('/admin/users')">
          <el-icon><Avatar /></el-icon>用户管理
        </el-button>
        <el-button type="success" @click="$router.push('/admin/clients')">
          <el-icon><Connection /></el-icon>客户端管理
        </el-button>
        <el-button type="warning" @click="$router.push('/admin/scopes')">
          <el-icon><Key /></el-icon>Scope 管理
        </el-button>
        <el-button type="info" @click="$router.push('/admin/webhooks')">
          <el-icon><Bell /></el-icon>Webhook 管理
        </el-button>
      </el-space>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Avatar, Connection, Key, Bell } from '@element-plus/icons-vue'
import { useAdminApi } from '@/composables/useAdminApi'

// 统计数据 SSR 预取
const { data } = await useAsyncData('admin-stats', async () => {
  try {
    const adminApi = useAdminApi()
    const [users, clients, scopes, webhooks] = await Promise.all([
      adminApi.listUsers({ limit: 1 }),
      adminApi.listClients({ limit: 1 }),
      adminApi.listScopes(),
      adminApi.listWebhooks(),
    ])
    return {
      userCount: users.total,
      clientCount: clients.total,
      scopeCount: scopes.length,
      webhookCount: webhooks.length,
    }
  } catch {
    return null
  }
})

const stats = computed(() => [
  { label: '用户总数', value: data.value?.userCount ?? '-', icon: Avatar, bg: '#e6f7ff', color: '#409EFF', link: '/admin/users' },
  { label: '客户端数', value: data.value?.clientCount ?? '-', icon: Connection, bg: '#f0f5ff', color: '#597ef7', link: '/admin/clients' },
  { label: 'Scope 数', value: data.value?.scopeCount ?? '-', icon: Key, bg: '#f6ffed', color: '#67C23A', link: '/admin/scopes' },
  { label: 'Webhook 数', value: data.value?.webhookCount ?? '-', icon: Bell, bg: '#fff7e6', color: '#E6A23C', link: '/admin/webhooks' },
])
</script>

<style lang="scss" scoped>
.admin-dashboard {
  .page-title {
    font-size: 24px;
    font-weight: 600;
    margin: 0;
    color: var(--el-text-color-primary);
  }

  .stat-card {
    cursor: pointer;
    :deep(.el-card__body) {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .stat-icon {
      width: 56px;
      height: 56px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .stat-info {
      .stat-value {
        font-size: 24px;
        font-weight: 700;
        color: var(--el-text-color-primary);
      }
      .stat-label {
        font-size: 13px;
        color: var(--el-text-color-secondary);
        margin-top: 2px;
      }
    }
  }

  .card-header {
    font-weight: 600;
    font-size: 15px;
  }
}
</style>
