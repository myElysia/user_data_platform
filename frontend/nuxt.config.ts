// ============================================================
// Nuxt 4 配置（SSR 模式，内置 Vite 构建）
// ============================================================

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  modules: ['@pinia/nuxt'],

  css: [
    'element-plus/dist/index.css',
    '~/assets/styles/variables.scss',
    '~/assets/styles/global.scss',
  ],

  build: {
    // Element Plus 在 SSR 下的互操作兼容
    transpile: ['element-plus'],
  },

  vite: {
    optimizeDeps: {
      // dayjs 的 main 入口是 dayjs.min.js（UMD），Vite 对 .min.js 视为已优化文件、
      // 原样透传不做 ESM 转换，浏览器将其作为 ESM 执行时没有任何导出，导致 Element Plus
      // 依赖链在客户端崩溃（报 "does not provide an export named 'default'"，页面点击无响应）；
      // 显式 include 强制 esbuild 预打包这些 UMD 入口，生成正确的 ESM 产物
      include: [
        'dayjs',
        'dayjs/plugin/customParseFormat.js',
        'dayjs/plugin/localeData.js',
        'dayjs/plugin/advancedFormat.js',
        'dayjs/plugin/weekOfYear.js',
        'dayjs/plugin/weekYear.js',
        'dayjs/plugin/dayOfYear.js',
        'dayjs/plugin/quarterOfYear.js',
        'dayjs/plugin/isSameOrAfter.js',
        'dayjs/plugin/isSameOrBefore.js',
      ],
    },
  },

  nitro: {
    externals: {
      // Windows + Node 22 下 @vercel/nft 的 readlink EISDIR 已知问题
      // （见 nuxt/nuxt#20915），禁用依赖追踪以绕过；仅影响 .output 依赖精简
      trace: false,
    },
  },

  runtimeConfig: {
    // SSR 端 $api 直连后端地址（生产部署时用环境变量 NUXT_API_BASE 覆盖）
    apiBase: 'http://127.0.0.1:8000',
  },

  routeRules: {
    // 后端 API 代理（开发/生产统一经 Nitro 转发到 FastAPI）
    '/api/**': { proxy: 'http://127.0.0.1:8000/api/**' },
    '/.well-known/**': { proxy: 'http://127.0.0.1:8000/.well-known/**' },
    // OIDC 动态客户端注册端点（RFC 7591，占用 /register 路径；
    // 前端用户注册页面已移至 /signup，避免路径冲突）
    '/register': { proxy: 'http://127.0.0.1:8000/register' },
    '/register/**': { proxy: 'http://127.0.0.1:8000/register/**' },
  },

  app: {
    head: {
      htmlAttrs: { lang: 'zh-CN' },
      title: 'Zero Trust OIDC Platform',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1.0' },
      ],
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/vite.svg' }],
    },
  },
})
