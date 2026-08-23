<template>
  <div class="admin-webhooks">
    <div class="page-header">
      <h1 class="page-title">Webhook 管理</h1>
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon>添加 Webhook
      </el-button>
    </div>

    <el-card shadow="never" style="margin-top: 16px" v-loading="pending">
      <el-empty v-if="!pending && webhooks.length === 0" description="暂无 Webhook 配置" />
      <el-table v-else :data="webhooks" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="event_type" label="事件类型" width="160">
          <template #default="{ row }">
            <el-tag type="primary">{{ row.event_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="url" label="URL" min-width="300" show-overflow-tooltip />
        <el-table-column prop="is_active" label="状态" width="80">
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
      </el-table>
    </el-card>

    <!-- 创建对话框 -->
    <el-dialog v-model="showCreate" title="添加 Webhook" width="460px" destroy-on-close>
      <el-form :model="webhookForm" label-width="90px" label-position="left">
        <el-form-item label="事件类型" required>
          <el-select v-model="webhookForm.event_type" style="width: 100%">
            <el-option label="user.created" value="user.created" />
            <el-option label="user.updated" value="user.updated" />
            <el-option label="user.deleted" value="user.deleted" />
            <el-option label="client.created" value="client.created" />
            <el-option label="consent.granted" value="consent.granted" />
            <el-option label="consent.revoked" value="consent.revoked" />
          </el-select>
        </el-form-item>
        <el-form-item label="URL" required>
          <el-input v-model="webhookForm.url" placeholder="https://your-app.com/webhook" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useAdminApi } from '@/composables/useAdminApi'
import type { WebhookConfig } from '@/types'

const adminApi = useAdminApi()

// Webhook 列表 SSR 预取
const { data: webhooksData, pending, refresh: refreshWebhooks } = await useAsyncData(
  'admin-webhooks',
  async () => {
    try {
      return await adminApi.listWebhooks()
    } catch {
      return [] as WebhookConfig[]
    }
  },
  { default: () => [] as WebhookConfig[] },
)
const webhooks = computed(() => webhooksData.value)

const saving = ref(false)
const showCreate = ref(false)

const webhookForm = reactive({
  event_type: 'user.created',
  url: '',
})

async function handleCreate() {
  if (!webhookForm.event_type || !webhookForm.url) {
    ElMessage.warning('请填写完整信息')
    return
  }
  saving.value = true
  try {
    await adminApi.createWebhook({
      event_type: webhookForm.event_type,
      url: webhookForm.url,
    })
    ElMessage.success('Webhook 已创建')
    showCreate.value = false
    webhookForm.url = ''
    await refreshWebhooks()
  } catch {
    // handled by interceptor
  } finally {
    saving.value = false
  }
}
</script>

<style lang="scss" scoped>
.admin-webhooks {
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
