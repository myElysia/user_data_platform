<template>
  <div class="login-view">
    <h2 class="form-title">登录</h2>
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      @submit.prevent="onSubmit"
    >
      <el-form-item prop="email">
        <el-input
          v-model="form.email"
          placeholder="请输入邮箱"
          :prefix-icon="Message"
          size="large"
        />
      </el-form-item>
      <el-form-item prop="password">
        <el-input
          v-model="form.password"
          type="password"
          placeholder="请输入密码"
          :prefix-icon="Lock"
          show-password
          size="large"
        />
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="form.rememberMe">记住我（7天免登录）</el-checkbox>
      </el-form-item>
      <el-form-item>
        <el-button
          type="primary"
          size="large"
          :loading="auth.loading"
          @click="onSubmit"
          style="width: 100%"
        >
          登 录
        </el-button>
      </el-form-item>
    </el-form>
    <div class="social-login">
      <el-divider class="social-divider">其他登录方式</el-divider>
      <div class="social-buttons">
        <el-button
          size="large"
          class="github-btn"
          @click="socialLogin('github')"
        >
          <svg class="github-icon" viewBox="0 0 16 16" width="18" height="18" aria-hidden="true">
            <path
              fill="currentColor"
              d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"
            />
          </svg>
          使用 GitHub 登录
        </el-button>
      </div>
    </div>
    <div class="form-footer">
      还没有账号？<NuxtLink to="/signup">立即注册</NuxtLink>
    </div>

    <!-- MFA 挑战对话框（风险引擎判定中风险时触发） -->
    <el-dialog
      v-model="mfaDialogVisible"
      title="多因素认证"
      width="380px"
      :close-on-click-modal="false"
      append-to-body
    >
      <p class="mfa-tip">
        {{ mfaChallengeMethod === 'totp' ? '请输入身份验证器中的 6 位动态码' : '验证码已发送至您的邮箱（未配置 SMTP 时请查看后端日志）' }}
      </p>
      <el-input
        v-model="mfaCode"
        :maxlength="6"
        placeholder="请输入验证码"
        size="large"
        @keyup.enter="submitMfa"
      />
      <template #footer>
        <el-button @click="mfaDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="auth.loading" @click="submitMfa">验证并登录</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Message, Lock } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuth } from '@/composables/useAuth'

definePageMeta({ layout: 'auth' })

const route = useRoute()
const { auth, handleLogin, handleMfaLogin } = useAuth()
const formRef = ref<FormInstance>()

// MFA 挑战状态
const mfaDialogVisible = ref(false)
const mfaCode = ref('')
const mfaChallengeToken = ref('')
const mfaChallengeMethod = ref('email_code')
const mfaRememberMe = ref(false)

// 第三方登录失败回调提示
onMounted(() => {
  if (route.query.social_error) {
    ElMessage.error(`第三方登录失败：${route.query.social_error}`)
  }
})

const form = reactive({
  email: '',
  password: '',
  rememberMe: false,
})

const rules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少 8 位', trigger: 'blur' },
  ],
}

async function onSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  const res = await handleLogin(form.email, form.password, form.rememberMe)
  if (res?.mfaRequired) {
    mfaChallengeToken.value = res.challengeToken || ''
    mfaChallengeMethod.value = res.challengeMethod || 'email_code'
    mfaRememberMe.value = form.rememberMe
    mfaCode.value = ''
    mfaDialogVisible.value = true
  }
}

/** 提交 MFA 验证码完成登录 */
async function submitMfa() {
  if (!mfaCode.value) {
    ElMessage.warning('请输入验证码')
    return
  }
  await handleMfaLogin(mfaChallengeToken.value, mfaCode.value, mfaRememberMe.value)
  mfaDialogVisible.value = false
}

/** 第三方登录：跳转 Nitro 授权路由（浏览器 302 到第三方平台，
 *  授权后回调 /social/{provider}/callback 页面完成登录） */
function socialLogin(provider: string) {
  window.location.href = `/auth/social/${provider}/authorize`
}
</script>

<style lang="scss" scoped>
.login-view {
  .form-title {
    font-size: 18px;
    text-align: center;
    margin-bottom: 24px;
    color: #303133;
  }

  .form-footer {
    text-align: center;
    font-size: 13px;
    color: #909399;

    a {
      color: #409EFF;
      text-decoration: none;
      &:hover { text-decoration: underline; }
    }
  }

  .social-login {
    margin-top: 8px;
    .social-divider {
      font-size: 12px;
      color: #909399;

      :deep(.el-divider__text) {
        background: #fff;
      }
    }

    .social-buttons {
      display: flex;
      justify-content: center;
      margin-top: 8px;

      .github-btn {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        width: 100%;
        color: #24292f;
        background: #f6f8fa;
        border: 1px solid #d0d7de;

        &:hover {
          background: #f3f4f6;
          border-color: #b8c0ca;
          color: #24292f;
        }

        .github-icon {
          flex-shrink: 0;
        }
      }
    }
  }
}
</style>
