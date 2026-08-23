// ============================================================
// Admin API — 基于全局 $api 客户端（ofetch）
// ============================================================

import type {
  PaginatedUsers,
  AdminUser,
  PaginatedClients,
  OAuthClient,
  AdminScope,
  WebhookConfig,
} from '@/types'

export function useAdminApi() {
  const api = useNuxtApp().$api

  return {
    // ---- 用户管理 ----

    listUsers(query?: {
      skip?: number
      limit?: number
      email?: string
      is_active?: boolean
    }) {
      return api<PaginatedUsers>('/api/admin/users', { query })
    },

    getUser(userId: number) {
      return api<AdminUser>(`/api/admin/users/${userId}`)
    },

    updateUser(
      userId: number,
      data: { display_name?: string; email?: string; phone?: string; country?: string; language?: string },
    ) {
      return api<AdminUser>(`/api/admin/users/${userId}`, { method: 'PUT', body: data })
    },

    toggleUser(userId: number) {
      return api<{ message: string; is_active: boolean }>(`/api/admin/users/${userId}/toggle`, {
        method: 'PUT',
      })
    },

    resetUserPassword(userId: number, newPassword: string) {
      return api<{ message: string }>(`/api/admin/users/${userId}/reset-password`, {
        method: 'PUT',
        query: { new_password: newPassword },
      })
    },

    deleteUser(userId: number) {
      return api<{ message: string }>(`/api/admin/users/${userId}`, { method: 'DELETE' })
    },

    batchDeleteUsers(userIds: number[]) {
      return api<{ message: string; deleted_ids: number[] }>('/api/admin/users/batch', {
        method: 'DELETE',
        body: { user_ids: userIds },
      })
    },

    // ---- 客户端管理 ----

    listClients(query?: { skip?: number; limit?: number; is_active?: boolean }) {
      return api<PaginatedClients>('/api/admin/clients', { query })
    },

    getClient(clientId: string) {
      return api<OAuthClient>(`/api/admin/clients/${clientId}`)
    },

    verifyClient(clientId: string) {
      return api<{ message: string }>(`/api/admin/clients/${clientId}/verify`, { method: 'PUT' })
    },

    toggleClient(clientId: string) {
      return api<{ message: string; is_active: boolean }>(`/api/admin/clients/${clientId}/toggle`, {
        method: 'PUT',
      })
    },

    // ---- Scopes ----

    listScopes() {
      return api<AdminScope[]>('/api/admin/scopes')
    },

    createScope(data: { name: string; description?: string }) {
      return api<AdminScope>('/api/admin/scopes', { method: 'POST', body: data })
    },

    deleteScope(scopeName: string) {
      return api<{ message: string }>(`/api/admin/scopes/${scopeName}`, { method: 'DELETE' })
    },

    // ---- Webhooks ----

    listWebhooks() {
      return api<WebhookConfig[]>('/api/webhooks')
    },

    createWebhook(data: { event_type: string; url: string }) {
      return api<WebhookConfig>('/api/webhooks', { method: 'POST', body: data })
    },

    getWebhookDeliveries(configId: number) {
      return api<any[]>(`/api/webhooks/${configId}/deliveries`)
    },
  }
}
