<template>
  <div class="profile">
    <h1 class="page-title">个人资料</h1>

    <el-row :gutter="20" style="margin-top: 20px">
      <!-- 基本信息 -->
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>基本信息</span>
              <el-button type="primary" size="small" @click="saveProfile" :loading="saving">保存</el-button>
            </div>
          </template>
          <el-form :model="profileForm" label-width="100px" label-position="left">
            <el-form-item label="邮箱">
              <el-input v-model="profileForm.email" disabled />
            </el-form-item>
            <el-form-item label="昵称">
              <el-input v-model="profileForm.display_name" maxlength="50" />
            </el-form-item>
            <el-form-item label="手机号">
              <el-input v-model="profileForm.phone" placeholder="选填" />
            </el-form-item>
            <el-form-item label="国家/地区">
              <el-input v-model="profileForm.country" maxlength="100" />
            </el-form-item>
            <el-form-item label="语言">
              <el-select v-model="profileForm.language">
                <el-option label="简体中文" value="zh-CN" />
                <el-option label="English" value="en-US" />
                <el-option label="日本語" value="ja-JP" />
              </el-select>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 安全信息 -->
      <el-col :span="10">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>安全设置</span>
            </div>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="邮箱验证">
              <el-tag :type="authStore.user?.email_verified ? 'success' : 'warning'" size="small">
                {{ authStore.user?.email_verified ? '已验证' : '未验证' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="手机验证">
              <el-tag :type="authStore.user?.phone_verified ? 'success' : 'warning'" size="small">
                {{ authStore.user?.phone_verified ? '已验证' : '未验证' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="注册时间">
              {{ authStore.user?.created_at ? new Date(authStore.user.created_at).toLocaleDateString() : '-' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card shadow="never" style="margin-top: 16px">
          <template #header>
            <div class="card-header">
              <span>修改密码</span>
            </div>
          </template>
          <el-form :model="passwordForm" label-width="80px" label-position="left">
            <el-form-item label="旧密码">
              <el-input v-model="passwordForm.old_password" type="password" show-password />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input v-model="passwordForm.new_password" type="password" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="changePassword" :loading="changingPwd">修改密码</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useAuthApi } from '@/composables/useAuthApi'

const authStore = useAuthStore()
const authApi = useAuthApi()
const saving = ref(false)
const changingPwd = ref(false)

const profileForm = reactive({
  email: '',
  display_name: '',
  phone: '',
  country: '',
  language: '',
})

const passwordForm = reactive({
  old_password: '',
  new_password: '',
})

onMounted(() => {
  const u = authStore.user
  if (u) {
    profileForm.email = u.email
    profileForm.display_name = u.display_name || ''
    profileForm.phone = u.phone || ''
    profileForm.country = u.country || ''
    profileForm.language = u.language || 'zh-CN'
  }
})

async function saveProfile() {
  saving.value = true
  try {
    await authApi.updateProfile({
      display_name: profileForm.display_name,
      phone: profileForm.phone,
      country: profileForm.country,
      language: profileForm.language,
    })
    await authStore.fetchProfile()
    ElMessage.success('资料已更新')
  } catch {
    // handled by interceptor
  } finally {
    saving.value = false
  }
}

async function changePassword() {
  if (!passwordForm.old_password || !passwordForm.new_password) {
    ElMessage.warning('请填写完整密码信息')
    return
  }
  if (passwordForm.new_password.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  changingPwd.value = true
  try {
    await authApi.changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
    })
    ElMessage.success('密码已修改')
    passwordForm.old_password = ''
    passwordForm.new_password = ''
  } catch {
    // handled by interceptor
  } finally {
    changingPwd.value = false
  }
}
</script>

<style lang="scss" scoped>
.profile {
  .page-title {
    font-size: 24px;
    font-weight: 600;
    margin: 0;
    color: var(--el-text-color-primary);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    font-size: 15px;
  }
}
</style>
