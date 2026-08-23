// ============================================================
// OAuth / Consent API — 基于全局 $api 客户端（ofetch）
// ============================================================

import type {
  OAuthClient,
  OAuthClientSecret,
  ClientRegisterRequest,
  ClientUpdateRequest,
  ConsentRecord,
} from '@/types'

export function useOauthApi() {
  const api = useNuxtApp().$api

  return {
    /** 注册 OAuth 客户端（OIDC 动态客户端注册，RFC 7591） */
    registerClient(data: ClientRegisterRequest) {
      return api<OAuthClientSecret>('/register', { method: 'POST', body: data })
    },

    /** 列出我的 OAuth 客户端 */
    listClients() {
      return api<OAuthClient[]>('/register')
    },

    /** 获取客户端详情 */
    getClient(clientId: string) {
      return api<OAuthClient>(`/register/${clientId}`)
    },

    /** 更新客户端 */
    updateClient(clientId: string, data: ClientUpdateRequest) {
      return api<OAuthClient>(`/register/${clientId}`, { method: 'PUT', body: data })
    },

    /** 删除客户端 */
    deleteClient(clientId: string) {
      return api<{ message: string }>(`/register/${clientId}`, { method: 'DELETE' })
    },

    /** 轮换密钥 */
    rotateSecret(clientId: string) {
      return api<OAuthClientSecret>(`/register/${clientId}/rotate-secret`, { method: 'POST' })
    },
  }
}

export function useConsentApi() {
  const api = useNuxtApp().$api

  return {
    /** 列出已授权应用 */
    listConsents() {
      return api<ConsentRecord[]>('/api/v1/consent')
    },

    /** 撤销单个授权 */
    revokeConsent(consentId: number) {
      return api<{ message: string }>(`/api/v1/consent/${consentId}`, { method: 'DELETE' })
    },

    /** 撤销对某客户端的所有授权 */
    revokeClientConsent(clientId: string) {
      return api<{ message: string }>(`/api/v1/consent/client/${clientId}`, { method: 'DELETE' })
    },
  }
}
