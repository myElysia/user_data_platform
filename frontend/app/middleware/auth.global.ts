// ============================================================
// 全局认证守卫 — 对应原 vue-router beforeEach
// 服务端渲染与客户端导航均生效（token 存于 cookie）
// ============================================================

export default defineNuxtRouteMiddleware((to) => {
  const token = useCookie<string | null>('access_token', { sameSite: 'lax' }).value

  // 公共页面（登录/注册）
  const isGuestPage = to.path === '/login' || to.path === '/signup'

  // 未登录访问受保护页面 → 登录页
  if (!isGuestPage && !token) {
    return navigateTo({ path: '/login', query: { redirect: to.fullPath } })
  }

  // 已登录访问登录/注册页 → 首页
  if (isGuestPage && token) {
    return navigateTo('/')
  }

  // 管理页面需要管理员账号
  if (to.path.startsWith('/admin')) {
    const userCookie = useCookie<{ email?: string } | null>('user', { sameSite: 'lax' }).value
    if (!userCookie || userCookie.email !== 'admin@zerotrust.local') {
      return navigateTo('/')
    }
  }
})
