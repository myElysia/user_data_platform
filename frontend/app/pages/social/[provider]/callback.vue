<template>
  <div class="social-callback-view">
    <el-result
      :icon="errorMsg ? 'error' : 'info'"
      :title="errorMsg ? '第三方登录失败' : '正在处理第三方登录...'"
      :sub-title="errorMsg || '请稍候，正在完成认证'"
    >
      <template v-if="errorMsg" #extra>
        <el-button type="primary" @click="navigateTo('/login')">返回登录</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import type { AuthResponse } from '@/types'

definePageMeta({ layout: 'auth' })

const route = useRoute()
const auth = useAuthStore()
const errorMsg = ref('')

onMounted(async () => {
  const provider = route.params.provider as string
  const { code, state } = route.query
  if (!code || !state) {
    errorMsg.value = '缺少授权回调参数'
    return
  }
  try {
    // 经 Nitro 代理直通后端 callback（返回 JSON 会话，不再经过浏览器 302）
    const res = await useNuxtApp().$api<AuthResponse>(
      `/api/v1/auth/social/${provider}/callback`,
      { query: { code: String(code), state: String(state) } },
    )
    if (res?.access_token) {
      auth.applySocialSession(res)
      ElMessage.success('登录成功')
      navigateTo('/')
      return
    }
    if (res?.mfa_required) {
      errorMsg.value = '该账号需要多因素认证，请改用密码登录'
      return
    }
    errorMsg.value = '第三方平台未返回会话'
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail || '第三方登录失败'
  }
})
</script>

<style lang="scss" scoped>
.social-callback-view {
  display: flex;
  justify-content: center;
}
</style>
