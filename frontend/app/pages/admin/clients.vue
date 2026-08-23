<template>
  <div class="admin-clients">
    <div class="page-header">
      <h1 class="page-title">客户端管理</h1>
      <el-button type="primary" @click="refreshClients" :loading="pending">
        <el-icon><Refresh /></el-icon>刷新
      </el-button>
    </div>

    <el-card shadow="never" style="margin-top: 16px" v-loading="pending">
      <el-table :data="clients" stripe>
        <el-table-column prop="client_id" label="Client ID" min-width="180" show-overflow-tooltip />
        <el-table-column prop="client_name" label="名称" min-width="140" />
        <el-table-column label="已验证" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_verified ? 'success' : 'warning'" size="small">
              {{ row.is_verified ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="!row.is_verified"
              size="small"
              type="primary"
              @click="handleVerify(row)"
            >
              验证
            </el-button>
            <el-button
              size="small"
              :type="row.is_active ? 'warning' : 'success'"
              @click="handleToggle(row)"
            >
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useAdminApi } from '@/composables/useAdminApi'
import type { OAuthClient } from '@/types'

const adminApi = useAdminApi()

// 客户端列表 SSR 预取
const { data: clientsData, pending, refresh: refreshClients } = await useAsyncData(
  'admin-clients',
  async () => {
    try {
      const res = await adminApi.listClients({ limit: 100 })
      return res.clients
    } catch {
      return [] as OAuthClient[]
    }
  },
  { default: () => [] as OAuthClient[] },
)
const clients = computed(() => clientsData.value)

async function handleVerify(client: OAuthClient) {
  try {
    await adminApi.verifyClient(client.client_id)
    ElMessage.success('客户端已验证')
    await refreshClients()
  } catch {
    // handled by interceptor
  }
}

async function handleToggle(client: OAuthClient) {
  try {
    const res = await adminApi.toggleClient(client.client_id)
    ElMessage.success(res.message)
    await refreshClients()
  } catch {
    // handled by interceptor
  }
}
</script>

<style lang="scss" scoped>
.admin-clients {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .page-title {
    font-size: 24px;
    font-weight: 600;
    margin: 0;
    color: var(--el-text-color-primary);
  }
}
</style>
