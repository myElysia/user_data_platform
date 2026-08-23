// ============================================================
// Auth Store — 登录状态管理
// token 存储由 localStorage 迁移为 cookie（SSR 服务端可读）
// ============================================================

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAuthApi } from '@/composables/useAuthApi'
import type { UserProfile, LoginRequest, RegisterRequest, AuthResponse } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const api = useAuthApi()

  // 会话级 cookie：未勾选"记住我"时关闭浏览器即失效；
  // 勾选后在 persistSession 中延迟覆盖为 7 天（见下方说明）
  const accessToken = useCookie<string | null>('access_token', { sameSite: 'lax' })
  const refreshToken = useCookie<string | null>('refresh_token', { sameSite: 'lax' })
  const user = useCookie<UserProfile | null>('user', { sameSite: 'lax' })
  const loading = ref(false)

  const isLoggedIn = computed(() => !!accessToken.value && !!user.value)
  const isAdmin = computed(() => user.value?.email === 'admin@zerotrust.local')

  /** 清理旧版 Vite SPA 的 localStorage 残留（仅客户端） */
  function clearLegacyStorage() {
    if (import.meta.client) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user')
    }
  }

  /** 原生写入持久 cookie（仅在客户端调用，用于"记住我"覆盖会话级 cookie） */
  function writePersistentCookie(name: string, value: string, maxAge: number) {
    document.cookie = `${name}=${encodeURIComponent(value)}; path=/; SameSite=Lax; Max-Age=${maxAge}`
  }

  /** 保存会话到 cookie（rememberMe 时全部 7 天，否则会话级） */
  function persistSession(token: string, rt: string | null, u: UserProfile, rememberMe = false) {
    // useCookie 默认写入会话级 cookie
    accessToken.value = token
    refreshToken.value = rt
    user.value = u
    if (import.meta.client && rememberMe) {
      // 注意：useCookie 的 watcher 在微任务中写回会话级 cookie，会覆盖此处的同步写入；
      // 因此延迟到宏任务（setTimeout 0）执行，确保 7 天 cookie 是最终值；
      // 再用 refreshCookie 广播同步所有 useCookie 实例
      setTimeout(() => {
        const maxAge = 60 * 60 * 24 * 7
        writePersistentCookie('access_token', token, maxAge)
        if (rt) writePersistentCookie('refresh_token', rt, maxAge)
        writePersistentCookie('user', JSON.stringify(u), maxAge)
        refreshCookie('access_token')
        refreshCookie('refresh_token')
        refreshCookie('user')
      }, 0)
    }
    clearLegacyStorage()
  }

  /** 清除会话 */
  function clearSession() {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
    clearLegacyStorage()
  }

  /** 登录 */
  async function login(data: LoginRequest) {
    loading.value = true
    try {
      const res = await api.login(data)
      // 风险引擎判定需要 MFA 挑战时，后端不返回 token，由调用方提示
      if (res.mfa_required) {
        return res
      }
      persistSession(res.access_token, res.refresh_token, res.user, data.remember_me)
      return res
    } finally {
      loading.value = false
    }
  }

  /** 注册 */
  async function register(data: RegisterRequest) {
    loading.value = true
    try {
      const res = await api.register(data)
      persistSession(res.access_token, res.refresh_token, res.user)
      return res
    } finally {
      loading.value = false
    }
  }

  /** MFA 登录第二步：挑战令牌 + 验证码/TOTP 换取正式会话 */
  async function completeMfa(challengeToken: string, code: string, rememberMe = false) {
    loading.value = true
    try {
      const res = await api.loginMfa({ mfa_challenge_token: challengeToken, code })
      persistSession(res.access_token, res.refresh_token, res.user, rememberMe)
      return res
    } finally {
      loading.value = false
    }
  }

  /** 第三方登录成功：写入会话 cookie（统一 7 天持久） */
  function applySocialSession(res: AuthResponse) {
    persistSession(res.access_token, res.refresh_token, res.user, true)
  }

  /** 登出 */
  async function logout() {
    try {
      await api.logout()
    } catch {
      // 即使远程失败，本地也清除
    } finally {
      clearSession()
    }
  }

  /** 刷新令牌（7 天免登录闭环：refresh_token 换新 access_token）
   *  成功返回 true；失败清除会话返回 false */
  async function refreshAuth(): Promise<boolean> {
    const rt = refreshToken.value
    if (!rt) return false
    try {
      const res = await api.refresh(rt)
      accessToken.value = res.access_token
      refreshToken.value = res.refresh_token
      user.value = res.user
      // 自动刷新后凭证跟随 refresh_token 的生命周期持久 7 天，
      // 保证"记住我"的免登录体验不因 access_token 24h 过期而中断
      if (import.meta.client) {
        setTimeout(() => {
          const maxAge = 60 * 60 * 24 * 7
          writePersistentCookie('access_token', res.access_token, maxAge)
          if (res.refresh_token) writePersistentCookie('refresh_token', res.refresh_token, maxAge)
          writePersistentCookie('user', JSON.stringify(res.user), maxAge)
          refreshCookie('access_token')
          refreshCookie('refresh_token')
          refreshCookie('user')
        }, 0)
      }
      clearLegacyStorage()
      return true
    } catch {
      clearSession()
      return false
    }
  }

  /** 拉取最新用户资料 */
  async function fetchProfile() {
    try {
      const profile = await api.getProfile()
      user.value = profile
    } catch {
      // ignore
    }
  }

  return {
    user,
    accessToken,
    refreshToken,
    loading,
    isLoggedIn,
    isAdmin,
    login,
    register,
    completeMfa,
    applySocialSession,
    logout,
    refreshAuth,
    fetchProfile,
    clearSession,
  }
})
