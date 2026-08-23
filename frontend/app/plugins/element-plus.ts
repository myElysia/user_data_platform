// ============================================================
// Element Plus 全量注册（zh-CN locale）
// ============================================================

import ElementPlus, { ID_INJECTION_KEY, ZINDEX_INJECTION_KEY } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.vueApp.use(ElementPlus, { locale: zhCn })
  // SSR 水合需要稳定的组件 ID / z-index（否则服务端与客户端渲染不一致导致 hydrate mismatch）
  nuxtApp.vueApp.provide(ID_INJECTION_KEY, {
    prefix: 1024,
    current: 0,
  })
  nuxtApp.vueApp.provide(ZINDEX_INJECTION_KEY, { current: 0 })
})
