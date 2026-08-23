<template>
  <div class="register-view">
    <h2 class="form-title">注册</h2>
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
      <el-form-item prop="displayName">
        <el-input
          v-model="form.displayName"
          placeholder="昵称（选填）"
          :prefix-icon="User"
          size="large"
        />
      </el-form-item>
      <el-form-item prop="password">
        <el-input
          v-model="form.password"
          type="password"
          placeholder="密码（至少 8 位，含大小写 + 数字 + 特殊字符）"
          :prefix-icon="Lock"
          show-password
          size="large"
        />
      </el-form-item>
      <el-form-item prop="confirmPassword">
        <el-input
          v-model="form.confirmPassword"
          type="password"
          placeholder="确认密码"
          :prefix-icon="Lock"
          show-password
          size="large"
        />
      </el-form-item>
      <el-form-item>
        <el-button
          type="primary"
          size="large"
          :loading="auth.loading"
          @click="onSubmit"
          style="width: 100%"
        >
          注 册
        </el-button>
      </el-form-item>
    </el-form>
    <div class="form-footer">
      已有账号？<NuxtLink to="/login">立即登录</NuxtLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { Message, Lock, User } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuth } from '@/composables/useAuth'

definePageMeta({ layout: 'auth' })

const { auth, handleRegister } = useAuth()
const formRef = ref<FormInstance>()

const form = reactive({
  email: '',
  displayName: '',
  password: '',
  confirmPassword: '',
})

const validateConfirm = (_rule: any, value: string, callback: any) => {
  if (value !== form.password) {
    callback(new Error('两次密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少 8 位', trigger: 'blur' },
    {
      pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^a-zA-Z\d]).{8,}$/,
      message: '需包含大小写字母、数字和特殊字符',
      trigger: 'blur',
    },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

async function onSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  await handleRegister(form.email, form.password, form.displayName)
}
</script>

<style lang="scss" scoped>
.register-view {
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
}
</style>
