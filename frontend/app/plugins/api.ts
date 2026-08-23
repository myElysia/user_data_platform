// ============================================================
// $api — 全局 API 客户端（ofetch 实例）
// 客户端：同源请求经 Nitro routeRules 代理到后端
// SSR 端：$fetch 直连后端（useRequestFetch 返回的实例无 .create，
//         无法挂 hooks；后端地址经 runtimeConfig.apiBase 可配置）
// ============================================================

import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

export default defineNuxtPlugin(() => {
  // 认证 token 存于 cookie（SSR/CSR 均可读）
  const token = useCookie<string | null>('access_token', { sameSite: 'lax' })
  const refreshToken = useCookie<string | null>('refresh_token', { sameSite: 'lax' })
  const user = useCookie<string | null>('user', { sameSite: 'lax' })

  const config = useRuntimeConfig()

  /** 并发 401 只触发一次刷新（防重入） */
  let refreshing = false

  /** 清除会话并跳转登录页（仅客户端） */
  function clearAndRedirect() {
    token.value = null
    refreshToken.value = null
    user.value = null
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
  }

  /** 静默刷新：refresh_token 换新 access_token，成功后整页重载 */
  function refreshAndReload() {
    if (refreshing) return
    refreshing = true
    const authStore = useAuthStore()
    authStore
      .refreshAuth()
      .then((ok) => {
        if (ok) {
          // 原请求已失败，重载后以新 token 重新发起（含 SSR 数据）
          window.location.reload()
        }
      })
      .finally(() => {
        refreshing = false
      })
  }

  const api = $fetch.create({
    // 客户端必须用绝对 URL：某些浏览器用户脚本会包装 window.fetch 并对
    // 相对路径 new URL() 失败（Failed to construct 'URL': Invalid URL），
    // 导致所有请求发不出去；绝对 URL 可兼容任意 fetch 包装
    baseURL: import.meta.server ? (config.apiBase as string) : window.location.origin,
    timeout: 15000,

    // 请求拦截：自动附加 Bearer token（已显式指定 Authorization 时不覆盖，
    // 例如 refresh 接口需携带 refresh_token 而非 access_token）
    onRequest({ options }) {
      if (token.value) {
        const headers = new Headers(options.headers as HeadersInit)
        if (!headers.get('Authorization')) {
          headers.set('Authorization', `Bearer ${token.value}`)
        }
        options.headers = headers
      }
    },

    // 响应拦截：统一错误处理
    onResponseError({ request, response }) {
      const status = response.status
      const data = response._data

      if (status === 401) {
        if (import.meta.client) {
          // refresh 接口自身 401：refresh_token 已失效，只能重新登录
          if (String(request).includes('/auth/refresh')) {
            clearAndRedirect()
            return
          }
          // 其他接口 401：优先用 refresh_token 静默刷新（7 天免登录闭环）
          if (refreshToken.value) {
            refreshAndReload()
            return
          }
          clearAndRedirect()
        }
        // SSR 端 401：不操作，交由客户端刷新链处理
      } else if (import.meta.client) {
        if (status === 403) {
          ElMessage.error('权限不足')
        } else if (status === 409) {
          ElMessage.error(data?.detail || '资源冲突')
        } else if (status >= 500) {
          ElMessage.error(data?.error || '服务器内部错误')
        }
      }
    },
  })

  return {
    provide: {
      api,
    },
  }
})
