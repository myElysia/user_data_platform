// ============================================================
// 客户端启动时静默刷新过期 access_token（7 天免登录兜底链）
// ============================================================
import { isTokenExpired } from '@/utils/auth'
import { useAuthStore } from '@/stores/auth'

export default defineNuxtPlugin(async () => {
  const auth = useAuthStore()

  // 无 refresh_token 或 access_token 仍有效 → 无需刷新
  if (!auth.refreshToken) return
  if (!isTokenExpired(auth.accessToken)) return

  const ok = await auth.refreshAuth()
  if (ok) {
    // 刷新成功后重载一次，让 SSR 数据以新 token 重新渲染
    window.location.reload()
  }
})
