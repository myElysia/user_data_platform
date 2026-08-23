// ============================================================
// 社交登录授权跳转（Nitro 路由，非 /api 路径 → 不被 routeRules 代理抢占）
//
// 流程：浏览器 → 本路由 → 直连后端换取授权地址（透传原始 Host 与自定义
// redirect_uri）→ 浏览器 302 跳转第三方平台 → 授权后回调
// /social/{provider}/callback 页面 → 页面调后端 callback 换取会话
// ============================================================

import {
  createError,
  defineEventHandler,
  getRouterParam,
  sendRedirect,
} from 'h3'
import { useRuntimeConfig } from '#imports'
import { $fetch } from 'ofetch'

export default defineEventHandler(async (event) => {
  const provider = getRouterParam(event, 'provider') || 'github'
  const config = useRuntimeConfig()

  // 前端自身地址 → 自定义回调页（GitHub OAuth App 需登记一致的 redirect_uri）
  const proto = event.node.req.headers['x-forwarded-proto'] || 'http'
  const host = event.node.req.headers.host || 'localhost:3000'
  const redirectUri = `${proto}://${host}/social/${provider}/callback`

  try {
    const res = await $fetch.raw(
      `${config.apiBase}/api/v1/auth/social/${provider}/authorize`,
      {
        redirect: 'manual',
        query: { redirect_uri: redirectUri },
        headers: {
          // 透传原始 Host → 后端 request.base_url 指向前端（默认回调地址兜底一致）
          host,
        },
      },
    )
    const location = res.headers.get('location')
    if (location) {
      return sendRedirect(event, location)
    }
    throw createError({
      statusCode: 502,
      statusMessage: 'Social provider returned no redirect',
    })
  } catch (e: any) {
    // ofetch 对 3xx（redirect: manual）会抛 FetchError：从响应头提取 Location
    const location = e?.response?.headers?.get?.('location')
    if (location) {
      return sendRedirect(event, location)
    }
    throw createError({
      statusCode: e?.statusCode || 502,
      statusMessage: e?.statusMessage || 'Social authorize failed',
    })
  }
})
