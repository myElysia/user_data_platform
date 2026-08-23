// ============================================================
// JWT token 工具 — 过期检测（用于 7 天免登录的自动刷新判定）
// ============================================================

/** base64url 解码（浏览器 atob / Node Buffer 双兼容） */
function decodeBase64Url(input: string): string {
  const b64 = input.replace(/-/g, '+').replace(/_/g, '/')
  if (typeof atob !== 'undefined') return atob(b64)
  return Buffer.from(b64, 'base64').toString('utf-8')
}

/**
 * 判断 JWT 是否已过期（或即将在 skewSeconds 秒内过期）
 * 解析失败视为过期（保守处理，触发刷新链）
 */
export function isTokenExpired(token: string | null | undefined, skewSeconds = 60): boolean {
  if (!token) return true
  try {
    const payload = token.split('.')[1]
    if (!payload) return true
    const json = JSON.parse(decodeBase64Url(payload))
    const exp = Number(json?.exp)
    if (!exp) return true
    return exp * 1000 < Date.now() + skewSeconds * 1000
  } catch {
    return true
  }
}
