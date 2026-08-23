<template>
  <div class="auth-layout">
    <div class="auth-card">
      <div class="auth-brand">
        <el-icon :size="40" color="#409EFF"><Monitor /></el-icon>
        <h1>Zero Trust OIDC</h1>
        <p>零信任用户中台</p>
      </div>
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Monitor } from '@element-plus/icons-vue'
</script>

<style lang="scss" scoped>
.auth-layout {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

  .auth-card {
    width: 420px;
    padding: 40px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);

    .auth-brand {
      text-align: center;
      margin-bottom: 32px;

      h1 {
        font-size: 22px;
        margin: 12px 0 4px;
        color: #303133;
      }

      p {
        font-size: 13px;
        color: #909399;
        margin: 0;
      }
    }
  }
}
</style>
