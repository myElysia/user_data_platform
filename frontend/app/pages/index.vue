<template>
  <div class="dashboard">
    <h1 class="page-title">仪表盘</h1>
    <p class="page-subtitle">欢迎回来，{{ authStore.user?.display_name || authStore.user?.email }}</p>

    <el-row :gutter="20" style="margin-top: 24px">
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #e6f7ff">
            <el-icon :size="28" color="#409EFF"><Connection /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ appCount }}</div>
            <div class="stat-label">OAuth 应用</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #f0f5ff">
            <el-icon :size="28" color="#597ef7"><Check /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ consentCount }}</div>
            <div class="stat-label">已授权应用</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #f6ffed">
            <el-icon :size="28" color="#67C23A"><User /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ authStore.user?.is_active ? '活跃' : '禁用' }}</div>
            <div class="stat-label">账户状态</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>快速操作</span>
        </div>
      </template>
      <el-space wrap>
        <el-button type="primary" @click="$router.push('/oauth-apps')">
          <el-icon><Plus /></el-icon>注册 OAuth 应用
        </el-button>
        <el-button @click="$router.push('/authorized-apps')">
          <el-icon><Check /></el-icon>管理授权
        </el-button>
        <el-button @click="$router.push('/profile')">
          <el-icon><User /></el-icon>编辑资料
        </el-button>
        <el-button v-if="authStore.isAdmin" type="warning" @click="$router.push('/admin')">
          <el-icon><DataAnalysis /></el-icon>管理面板
        </el-button>
      </el-space>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { Connection, Check, User, Plus, DataAnalysis } from '@element-plus/icons-vue'

const authStore = useAuthStore()

// SSR 端预取统计数据（服务端渲染时即携带数据）
const { data } = await useAsyncData('dashboard-stats', async () => {
  try {
    const [clients, consents] = await Promise.all([
      useOauthApi().listClients(),
      useConsentApi().listConsents(),
    ])
    return { appCount: clients.length, consentCount: consents.length }
  } catch {
    return { appCount: 0, consentCount: 0 }
  }
})

const appCount = computed(() => data.value?.appCount ?? 0)
const consentCount = computed(() => data.value?.consentCount ?? 0)
</script>

<style lang="scss" scoped>
.dashboard {
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

  .stat-card {
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
