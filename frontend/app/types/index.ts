// ============================================================
// 数据类型定义 — 与后端 schemas 对齐
// ============================================================

/** 用户资料 */
export interface UserProfile {
  id: number
  email: string
  display_name: string | null
  phone: string | null
  country: string | null
  language: string | null
  icon: string | null
  email_verified: boolean
  phone_verified: boolean
  is_active: boolean
  created_at: string
}

/** 认证响应 */
export interface AuthResponse {
  user: UserProfile
  access_token: string
  refresh_token: string | null
  token_type: string
  expires_in: number
  /** 风险引擎判定需要 MFA 挑战时返回 true（此时无 token） */
  mfa_required?: boolean
  mfa_challenge_token?: string
  /** 挑战方式：totp / email_code */
  challenge_method?: string
}

/** MFA 登录第二步请求 */
export interface MfaLoginRequest {
  mfa_challenge_token: string
  code: string
}

/** 注册请求 */
export interface RegisterRequest {
  email: string
  password: string
  display_name?: string
  country?: string
  language?: string
}

/** 登录请求 */
export interface LoginRequest {
  email: string
  password: string
  remember_me?: boolean
}

/** 修改密码请求 */
export interface ChangePasswordRequest {
  old_password: string
  new_password: string
}

/** 更新资料请求 */
export interface ProfileUpdateRequest {
  display_name?: string
  phone?: string
  language?: string
  country?: string
  icon?: string
}

// ---- OAuth 客户端 ----

export interface OAuthClient {
  client_id: string
  client_name: string
  description: string | null
  redirect_uris: string[]
  grant_types: string[]
  scopes: string[]
  homepage_url: string | null
  logo_url: string | null
  owner_id?: number
  is_active: boolean
  is_verified?: boolean
  created_at: string
  updated_at: string
}

export interface OAuthClientSecret extends OAuthClient {
  client_secret: string
}

export interface ClientRegisterRequest {
  client_name: string
  description?: string
  redirect_uris: string[]
  grant_types?: string[]
  scopes?: string[]
  token_endpoint_auth_method?: string
  homepage_url?: string
  logo_url?: string
}

export interface ClientUpdateRequest {
  client_name?: string
  description?: string
  redirect_uris?: string[]
  grant_types?: string[]
  scopes?: string[]
  homepage_url?: string
  logo_url?: string
  is_active?: boolean
}

// ---- 同意管理 ----

export interface ConsentRecord {
  id: number
  client_id: string
  scopes: string[]
  granted_at: string
  expires_at: string | null
  is_expired: boolean
}

// ---- 管理员 ----

export interface AdminUser {
  id: number
  email: string
  display_name: string | null
  phone: string | null
  country: string | null
  language: string | null
  email_verified: boolean
  phone_verified: boolean
  is_active: boolean
  created_at: string
  updated_at: string | null
  deleted_at: string | null
}

export interface PaginatedUsers {
  total: number
  skip: number
  limit: number
  users: AdminUser[]
}

export interface PaginatedClients {
  total: number
  clients: OAuthClient[]
}

export interface AdminScope {
  name: string
  description: string | null
  is_default: boolean
}

export interface WebhookConfig {
  id: number
  event_type: string
  url: string
  is_active: boolean
  created_at: string
}

// ---- 通用 ----

export interface ApiError {
  error: string
  code: string
  path: string
  request_id?: string
}
