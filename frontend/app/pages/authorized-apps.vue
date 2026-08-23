<template>
  <div class="authorized-apps">
    <div class="page-header">
      <div>
        <h1 class="page-title">已授权应用</h1>
        <p class="page-subtitle">管理已授权访问你账户的第三方应用</p>
      </div>
      <el-button type="primary" @click="refreshConsents" :loading="pending">
        <el-icon><Refresh /></el-icon>刷新
      </el-button>
    </div>

    <el-card shadow="never" style="margin-top: 20px" v-loading="pending">
      <el-empty v-if="!pending && consents.length === 0" description="暂无已授权应用" />
      <el-table v-else :data="consents" stripe>
        <el-table-column prop="client_id" label="Client ID" min-width="200">
          <template #default="{ row }">
            <el-tag type="info">{{ row.client_id }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="scopes" label="授权 Scope" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="s in row.scopes" :key="s" size="small" style="margin: 2px">{{ s }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="granted_at" label="授权时间" width="180">
          <template #default="{ row }">
            {{ new Date(row.granted_at).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column prop="is_expired" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_expired ? 'danger' : 'success'" size="small">
              {{ row.is_expired ? '已过期' : '有效' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-popconfirm
              title="确定撤销此授权？"
              @confirm="handleRevoke(row.id)"
            >
              <template #reference>
                <el-button size="small" type="danger">撤销</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useConsentApi } from '@/composables/useOauthApi'
import type { ConsentRecord } from '@/types'

const consentApi = useConsentApi()

// 授权列表 SSR 预取
const { data: consentsData, pending, refresh: refreshConsents } = await useAsyncData(
  'authorized-apps',
  async () => {
    try {
      return await consentApi.listConsents()
    } catch {
      return [] as ConsentRecord[]
    }
  },
  { default: () => [] as ConsentRecord[] },
)
const consents = computed(() => consentsData.value)

async function handleRevoke(consentId: number) {
  try {
    await consentApi.revokeConsent(consentId)
    ElMessage.success('已撤销授权')
    await refreshConsents()
  } catch {
    // handled by interceptor
  }
}
</script>

<style lang="scss" scoped>
.authorized-apps {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }

  .page-title {
    font-size: 24px;
    font-weight: 600;
    margin: 0 0 4px;
    color: var(--el-text-color-primary);
  }

  .page-subtitle {
    margin: 0;
    color: var(--el-text-color-secondary);
    font-size: 14px;
  }
}
</style>
