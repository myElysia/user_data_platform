<template>
  <div class="oauth-apps">
    <div class="page-header">
      <div>
        <h1 class="page-title">OAuth 应用</h1>
        <p class="page-subtitle">管理你的 OAuth 客户端应用，类似 GitHub OAuth Apps</p>
      </div>
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon>注册新应用
      </el-button>
    </div>

    <!-- 应用列表 -->
    <el-card shadow="never" style="margin-top: 20px" v-loading="pending">
      <el-empty v-if="!pending && clients.length === 0" description="暂无 OAuth 应用" />
      <el-table v-else :data="clients" stripe>
        <el-table-column prop="client_name" label="应用名称" min-width="160">
          <template #default="{ row }">
            <div class="client-name-cell">
              <el-avatar :size="32" shape="square">
                <img v-if="row.logo_url" :src="row.logo_url" />
                <el-icon v-else><Grid /></el-icon>
              </el-avatar>
              <div>
                <div class="client-name">{{ row.client_name }}</div>
                <div class="client-id">{{ row.client_id }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="140" show-overflow-tooltip />
        <el-table-column prop="scopes" label="Scopes" width="120">
          <template #default="{ row }">
            <el-tag v-for="s in row.scopes" :key="s" size="small" style="margin: 2px">{{ s }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row)">详情</el-button>
            <el-button size="small" type="primary" @click="editClient(row)">编辑</el-button>
            <el-popconfirm title="确定删除此应用？" @confirm="handleDelete(row.client_id)">
              <template #reference>
                <el-button size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="showCreate"
      :title="editingClient ? '编辑应用' : '注册新应用'"
      width="560px"
      destroy-on-close
    >
      <el-form :model="clientForm" label-width="110px" label-position="left">
        <el-form-item label="应用名称" required>
          <el-input v-model="clientForm.client_name" maxlength="100" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="clientForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="回调 URL" required>
          <el-input
            v-model="redirectUriInput"
            placeholder="https://example.com/callback"
            @keyup.enter="addRedirectUri"
          >
            <template #append>
              <el-button @click="addRedirectUri">添加</el-button>
            </template>
          </el-input>
          <div style="margin-top: 8px">
            <el-tag
              v-for="(uri, idx) in clientForm.redirect_uris"
              :key="idx"
              closable
              @close="clientForm.redirect_uris.splice(idx, 1)"
              style="margin: 2px"
            >
              {{ uri }}
            </el-tag>
          </div>
        </el-form-item>
        <el-form-item label="Scopes">
          <el-checkbox-group v-model="clientForm.scopes">
            <el-checkbox label="openid" />
            <el-checkbox label="profile" />
            <el-checkbox label="email" />
            <el-checkbox label="phone" />
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="主页 URL">
          <el-input v-model="clientForm.homepage_url" placeholder="https://" />
        </el-form-item>
        <el-form-item label="Logo URL">
          <el-input v-model="clientForm.logo_url" placeholder="https://" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ editingClient ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 详情对话框 -->
    <el-dialog v-model="showDetail" title="应用详情" width="560px">
      <el-descriptions v-if="detailClient" :column="1" border>
        <el-descriptions-item label="Client ID">{{ detailClient.client_id }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ detailClient.client_name }}</el-descriptions-item>
        <el-descriptions-item label="描述">{{ detailClient.description || '-' }}</el-descriptions-item>
        <el-descriptions-item label="回调 URL">
          <div v-for="uri in detailClient.redirect_uris" :key="uri">{{ uri }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="Grant Types">
          <el-tag v-for="g in detailClient.grant_types" :key="g" size="small" style="margin: 2px">{{ g }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Scopes">
          <el-tag v-for="s in detailClient.scopes" :key="s" size="small" style="margin: 2px">{{ s }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detailClient.created_at }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 密钥显示 -->
    <el-dialog v-model="showSecret" title="新应用密钥" width="480px">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="请立即保存 Client Secret，此密钥仅显示一次！"
      />
      <el-descriptions :column="1" style="margin-top: 16px" border>
        <el-descriptions-item label="Client ID">
          <el-tag>{{ newSecret?.client_id }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Client Secret">
          <el-input :model-value="newSecret?.client_secret" readonly type="textarea" :rows="2" />
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Grid } from '@element-plus/icons-vue'
import { useOauthApi } from '@/composables/useOauthApi'
import type { OAuthClient, OAuthClientSecret } from '@/types'

const oauthApi = useOauthApi()

// 列表数据 SSR 预取
const { data: clientsData, pending, refresh: refreshClients } = await useAsyncData(
  'oauth-apps',
  async () => {
    try {
      return await oauthApi.listClients()
    } catch {
      return [] as OAuthClient[]
    }
  },
  { default: () => [] as OAuthClient[] },
)
const clients = computed(() => clientsData.value)

const saving = ref(false)
const showCreate = ref(false)
const showDetail = ref(false)
const showSecret = ref(false)
const editingClient = ref<OAuthClient | null>(null)
const detailClient = ref<OAuthClient | null>(null)
const newSecret = ref<OAuthClientSecret | null>(null)
const redirectUriInput = ref('')

const clientForm = reactive({
  client_name: '',
  description: '',
  redirect_uris: [] as string[],
  scopes: ['openid', 'profile', 'email'],
  homepage_url: '',
  logo_url: '',
})

function addRedirectUri() {
  const uri = redirectUriInput.value.trim()
  if (uri && !clientForm.redirect_uris.includes(uri)) {
    clientForm.redirect_uris.push(uri)
  }
  redirectUriInput.value = ''
}

function resetForm() {
  clientForm.client_name = ''
  clientForm.description = ''
  clientForm.redirect_uris = []
  clientForm.scopes = ['openid', 'profile', 'email']
  clientForm.homepage_url = ''
  clientForm.logo_url = ''
  editingClient.value = null
  redirectUriInput.value = ''
}

function editClient(client: OAuthClient) {
  resetForm()
  editingClient.value = client
  clientForm.client_name = client.client_name
  clientForm.description = client.description || ''
  clientForm.redirect_uris = [...client.redirect_uris]
  clientForm.scopes = [...client.scopes]
  clientForm.homepage_url = client.homepage_url || ''
  clientForm.logo_url = client.logo_url || ''
  showCreate.value = true
}

function viewDetail(client: OAuthClient) {
  detailClient.value = client
  showDetail.value = true
}

async function handleSave() {
  if (!clientForm.client_name || clientForm.redirect_uris.length === 0) {
    ElMessage.warning('请填写应用名称和回调 URL')
    return
  }
  saving.value = true
  try {
    if (editingClient.value) {
      await oauthApi.updateClient(editingClient.value.client_id, {
        client_name: clientForm.client_name,
        description: clientForm.description,
        redirect_uris: clientForm.redirect_uris,
        scopes: clientForm.scopes,
        homepage_url: clientForm.homepage_url,
        logo_url: clientForm.logo_url,
      })
      ElMessage.success('应用已更新')
    } else {
      const secret = await oauthApi.registerClient({
        client_name: clientForm.client_name,
        description: clientForm.description,
        redirect_uris: clientForm.redirect_uris,
        scopes: clientForm.scopes,
        grant_types: ['authorization_code', 'refresh_token'],
        homepage_url: clientForm.homepage_url,
        logo_url: clientForm.logo_url,
      })
      newSecret.value = secret
      showSecret.value = true
      ElMessage.success('应用已创建')
    }
    showCreate.value = false
    resetForm()
    await refreshClients()
  } catch {
    // handled by interceptor
  } finally {
    saving.value = false
  }
}

async function handleDelete(clientId: string) {
  try {
    await oauthApi.deleteClient(clientId)
    ElMessage.success('已删除')
    await refreshClients()
  } catch {
    // handled by interceptor
  }
}
</script>

<style lang="scss" scoped>
.oauth-apps {
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

  .client-name-cell {
    display: flex;
    align-items: center;
    gap: 10px;

    .client-name {
      font-weight: 500;
      font-size: 14px;
    }

    .client-id {
      font-size: 12px;
      color: var(--el-text-color-secondary);
      font-family: monospace;
    }
  }
}
</style>
