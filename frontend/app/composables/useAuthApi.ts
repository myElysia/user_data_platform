// ============================================================
// Auth API — 基于全局 $api 客户端（ofetch）
// ============================================================

import type {
  AuthResponse,
  RegisterRequest,
  LoginRequest,
  UserProfile,
  ChangePasswordRequest,
  ProfileUpdateRequest,
  MfaLoginRequest,
} from '@/types'

export function useAuthApi() {
  const api = useNuxtApp().$api

  return {
    /** 注册 */
    register(data: RegisterRequest) {
      return api<AuthResponse>('/api/v1/auth/register', { method: 'POST', body: data })
    },

    /** 登录 */
    login(data: LoginRequest) {
      return api<AuthResponse>('/api/v1/auth/login', { method: 'POST', body: data })
    },

    /** 登出 */
    logout() {
      return api<{ message: string }>('/api/v1/auth/logout', { method: 'POST' })
    },

    /** 刷新令牌 */
    refresh(refreshToken: string) {
      return api<AuthResponse>('/api/v1/auth/refresh', {
        method: 'POST',
        headers: { Authorization: `Bearer ${refreshToken}` },
      })
    },

    /** MFA 登录第二步（挑战令牌 + 验证码/TOTP） */
    loginMfa(data: MfaLoginRequest) {
      return api<AuthResponse>('/api/v1/auth/login/mfa', { method: 'POST', body: data })
    },

    /** 获取当前用户资料 */
    getProfile() {
      return api<UserProfile>('/api/v1/auth/profile')
    },

    /** 更新资料 */
    updateProfile(data: ProfileUpdateRequest) {
      return api<UserProfile>('/api/v1/auth/profile', { method: 'PUT', body: data })
    },

    /** 修改密码 */
    changePassword(data: ChangePasswordRequest) {
      return api<{ message: string }>('/api/v1/auth/change-password', { method: 'PUT', body: data })
    },
  }
}
