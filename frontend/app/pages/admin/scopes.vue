<template>
  <div class="admin-scopes">
    <div class="page-header">
      <h1 class="page-title">Scope 管理</h1>
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon>添加 Scope
      </el-button>
    </div>

    <el-card shadow="never" style="margin-top: 16px" v-loading="pending">
      <el-table :data="scopes" stripe>
        <el-table-column prop="name" label="名称" min-width="200">
          <template #default="{ row }">
            <el-tag>{{ row.name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="300" show-overflow-tooltip />
        <el-table-column prop="is_default" label="默认" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_default ? 'success' : 'info'" size="small">
              {{ row.is_default ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-popconfirm
              :title="`确定删除 Scope ${row.name} ？`"
              @confirm="handleDelete(row.name)"
            >
              <template #reference>
                <el-button size="small" type="danger" :disabled="row.is_default">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建对话框 -->
    <el-dialog v-model="showCreate" title="添加 Scope" width="420px" destroy-on-close>
      <el-form :model="scopeForm" label-width="80px" label-position="left">
        <el-form-item label="名称" required>
          <el-input v-model="scopeForm.name" placeholder="如: read:profile" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="scopeForm.description" placeholder="Scope 描述" />
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
import type { AdminScope } from '@/types'

const adminApi = useAdminApi()

// Scope 列表 SSR 预取
const { data: scopesData, pending, refresh: refreshScopes } = await useAsyncData(
  'admin-scopes',
  async () => {
    try {
      return await adminApi.listScopes()
    } catch {
      return [] as AdminScope[]
    }
  },
  { default: () => [] as AdminScope[] },
)
const scopes = computed(() => scopesData.value)

const saving = ref(false)
const showCreate = ref(false)

const scopeForm = reactive({
  name: '',
  description: '',
})

async function handleCreate() {
  if (!scopeForm.name) {
    ElMessage.warning('请输入 Scope 名称')
    return
  }
  saving.value = true
  try {
    await adminApi.createScope({
      name: scopeForm.name,
      description: scopeForm.description,
    })
    ElMessage.success('Scope 已创建')
    showCreate.value = false
    scopeForm.name = ''
    scopeForm.description = ''
    await refreshScopes()
  } catch {
    // handled by interceptor
  } finally {
    saving.value = false
  }
}

async function handleDelete(scopeName: string) {
  try {
    await adminApi.deleteScope(scopeName)
    ElMessage.success('已删除')
    await refreshScopes()
  } catch {
    // handled by interceptor
  }
}
</script>

<style lang="scss" scoped>
.admin-scopes {
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
