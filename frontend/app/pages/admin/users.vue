<template>
  <div class="admin-users">
    <div class="page-header">
      <h1 class="page-title">用户管理</h1>
      <div class="header-actions">
        <el-input
          v-model="searchEmail"
          placeholder="搜索邮箱..."
          clearable
          style="width: 220px"
          @clear="fetchUsers"
          @keyup.enter="fetchUsers"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="fetchUsers">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <el-card shadow="never" style="margin-top: 16px" v-loading="loading">
      <div class="batch-bar" v-if="selectedRows.length > 0">
        <span class="batch-tip">已选 {{ selectedRows.length }} 项</span>
        <el-popconfirm
          :title="`确定软删除选中的 ${selectedRows.length} 个用户？`"
          @confirm="handleBatchDelete"
        >
          <template #reference>
            <el-button type="danger" size="small">批量删除</el-button>
          </template>
        </el-popconfirm>
        <el-button size="small" @click="clearSelection">取消选择</el-button>
      </div>
      <el-table
        ref="tableRef"
        :data="users"
        stripe
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="45" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="display_name" label="昵称" min-width="120" />
        <el-table-column prop="country" label="国家/地区" width="100" />
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '活跃' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="email_verified" label="邮箱验证" width="90">
          <template #default="{ row }">
            <el-tag :type="row.email_verified ? 'success' : 'info'" size="small">
              {{ row.email_verified ? '已验证' : '未验证' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="注册时间" width="170">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editUser(row)">编辑</el-button>
            <el-dropdown trigger="click" @command="(cmd: string) => handleCommand(cmd, row)">
              <el-button size="small">更多<el-icon><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="toggle">
                    {{ row.is_active ? '禁用' : '启用' }}
                  </el-dropdown-item>
                  <el-dropdown-item command="reset-pwd">重置密码</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination" style="margin-top: 16px">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @change="fetchUsers"
        />
      </div>
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog v-model="showEdit" title="编辑用户" width="480px" destroy-on-close>
      <el-form :model="editForm" label-width="90px" label-position="left">
        <el-form-item label="邮箱">
          <el-input v-model="editForm.email" />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="editForm.display_name" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="editForm.phone" />
        </el-form-item>
        <el-form-item label="国家/地区">
          <el-input v-model="editForm.country" />
        </el-form-item>
        <el-form-item label="语言">
          <el-select v-model="editForm.language">
            <el-option label="简体中文" value="zh-CN" />
            <el-option label="English" value="en-US" />
            <el-option label="日本語" value="ja-JP" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSaveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, ArrowDown } from '@element-plus/icons-vue'
import { useAdminApi } from '@/composables/useAdminApi'
import type { AdminUser } from '@/types'

const adminApi = useAdminApi()

const loading = ref(false)
const saving = ref(false)
const users = ref<AdminUser[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchEmail = ref('')
const showEdit = ref(false)
const editingUserId = ref<number | null>(null)
const selectedRows = ref<AdminUser[]>([])
const tableRef = ref()

const editForm = reactive({
  email: '',
  display_name: '',
  phone: '',
  country: '',
  language: '',
})

async function fetchUsers() {
  loading.value = true
  try {
    const res = await adminApi.listUsers({
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
      email: searchEmail.value || undefined,
    })
    users.value = res.users
    total.value = res.total
  } catch {
    users.value = []
  } finally {
    loading.value = false
  }
}

function editUser(user: AdminUser) {
  editingUserId.value = user.id
  editForm.email = user.email
  editForm.display_name = user.display_name || ''
  editForm.phone = user.phone || ''
  editForm.country = user.country || ''
  editForm.language = user.language || ''
  showEdit.value = true
}

async function handleSaveEdit() {
  if (!editingUserId.value) return
  saving.value = true
  try {
    const res: any = await adminApi.updateUser(editingUserId.value, {
      email: editForm.email,
      display_name: editForm.display_name,
      phone: editForm.phone,
      country: editForm.country,
      language: editForm.language,
    })
    showEdit.value = false
    await fetchUsers()
    // 邮箱/手机号变更时后端已触发验证发送（ARQ），提示发送结果
    const sent = res?.verification?.sent as string[] | undefined
    if (sent?.length) {
      ElMessage.success(`已更新，验证发送：${sent.join('；')}`)
    } else {
      ElMessage.success('已更新')
    }
  } catch {
    // handled by interceptor
  } finally {
    saving.value = false
  }
}

function onSelectionChange(rows: AdminUser[]) {
  selectedRows.value = rows
}

function clearSelection() {
  tableRef.value?.clearSelection()
  selectedRows.value = []
}

async function handleBatchDelete() {
  const ids = selectedRows.value.map((r) => r.id)
  try {
    const res = await adminApi.batchDeleteUsers(ids)
    ElMessage.success(res.message)
    selectedRows.value = []
    await fetchUsers()
  } catch {
    // handled by interceptor
  }
}

/** 操作列下拉菜单命令分发（带确认提示） */
function handleCommand(cmd: string, row: AdminUser) {
  if (cmd === 'toggle') {
    handleToggle(row)
  } else if (cmd === 'reset-pwd') {
    ElMessageBox.confirm('确定重置密码？', '提示', { type: 'warning' }).then(() =>
      handleResetPwd(row),
    ).catch(() => {})
  } else if (cmd === 'delete') {
    ElMessageBox.confirm('确定软删除此用户？', '提示', { type: 'warning' }).then(() =>
      handleDelete(row.id),
    ).catch(() => {})
  }
}

async function handleToggle(user: AdminUser) {
  try {
    const res = await adminApi.toggleUser(user.id)
    ElMessage.success(res.message)
    await fetchUsers()
  } catch {
    // handled by interceptor
  }
}

async function handleResetPwd(user: AdminUser) {
  try {
    await adminApi.resetUserPassword(user.id, 'Reset@12345')
    ElMessage.success('密码已重置为 Reset@12345')
  } catch {
    // handled by interceptor
  }
}

async function handleDelete(userId: number) {
  try {
    await adminApi.deleteUser(userId)
    ElMessage.success('用户已禁用')
    await fetchUsers()
  } catch {
    // handled by interceptor
  }
}

onMounted(fetchUsers)
</script>

<style lang="scss" scoped>
.admin-users {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
  }

  .page-title {
    font-size: 24px;
    font-weight: 600;
    margin: 0;
    color: var(--el-text-color-primary);
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }

  .batch-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    margin-bottom: 12px;
    background: var(--el-color-danger-light-9);
    border-radius: 4px;

    .batch-tip {
      font-size: 13px;
      color: var(--el-color-danger);
    }
  }

  .pagination {
    display: flex;
    justify-content: flex-end;
  }
}
</style>
