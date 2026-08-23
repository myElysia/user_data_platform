// ============================================================
// useAuth composable — 封装认证相关逻辑
// ============================================================

import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

export function useAuth() {
  const auth = useAuthStore()
  const router = useRouter()

  /** 登录第一步：凭证校验。返回 mfa 挑战上下文或完成登录 */
  async function handleLogin(email: string, password: string, rememberMe = false) {
    try {
      const res = await auth.login({ email, password, remember_me: rememberMe })
      if (res.mfa_required) {
        // 风险引擎判定需要 MFA 挑战 → 返回挑战上下文，由页面弹验证码输入
        return {
          mfaRequired: true,
          challengeToken: res.mfa_challenge_token,
          challengeMethod: res.challenge_method,
        }
      }
      ElMessage.success('登录成功')
      const redirect = router.currentRoute.value.query.redirect as string
      router.push(redirect || '/')
      return { mfaRequired: false }
    } catch (e: any) {
      const msg = e?.response?.data?.detail || '登录失败'
      ElMessage.error(msg)
      throw e
    }
  }

  /** 登录第二步：MFA 验证码/TOTP 换取正式会话 */
  async function handleMfaLogin(challengeToken: string, code: string, rememberMe = false) {
    try {
      await auth.completeMfa(challengeToken, code, rememberMe)
      ElMessage.success('登录成功')
      const redirect = router.currentRoute.value.query.redirect as string
      router.push(redirect || '/')
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'MFA 验证失败'
      ElMessage.error(msg)
      throw e
    }
  }

  async function handleRegister(
    email: string,
    password: string,
    displayName?: string,
  ) {
    try {
      await auth.register({
        email,
        password,
        display_name: displayName || email.split('@')[0],
      })
      ElMessage.success('注册成功')
      router.push('/')
    } catch (e: any) {
      const msg = e?.response?.data?.detail || '注册失败'
      ElMessage.error(msg)
      throw e
    }
  }

  async function handleLogout() {
    await auth.logout()
    ElMessage.success('已登出')
    router.push('/login')
  }

  return {
    auth,
    handleLogin,
    handleMfaLogin,
    handleRegister,
    handleLogout,
  }
}
