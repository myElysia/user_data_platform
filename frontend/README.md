# Zero Trust OIDC Platform — 前端

零信任用户中台的 Web 前端，基于 Nuxt 4（SSR 模式，内嵌 Vite 构建）+ TypeScript + Pinia + Element Plus。提供登录/注册、个人资料、OAuth 应用管理、授权同意管理与管理后台（用户/客户端/Scope/Webhook）。

## 技术栈

| 分类 | 技术 |
| --- | --- |
| 框架 | Nuxt 4（SSR，`app/` 目录结构，兼容性日期 2025-07-15） |
| 构建 | Vite 7（Nuxt 内置）+ Nitro 服务端（routeRules 代理） |
| 语言 | TypeScript 5 + vue-tsc 类型检查 |
| 状态管理 | Pinia 3（@pinia/nuxt 模块） |
| UI 组件库 | Element Plus（SSR 全量注册 + zh-cn locale） |
| HTTP | ofetch（`$api` 插件：请求拦截注入 Bearer、响应统一错误处理） |
| 样式 | Sass（variables + global） |
| 路由 | Nuxt 文件路由 + `middleware/auth.global.ts` 全局守卫 |

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
# 国内网络建议使用镜像（registry.npmjs.org 延迟高）：
# npm install --registry https://registry.npmmirror.com
```

### 2. 启动开发服务器

```bash
npm run dev
# 默认 http://localhost:3000
```

后端请求经 Nitro `routeRules` 代理（见 `nuxt.config.ts`）转发至 `http://127.0.0.1:8000`：

- `/api/**` → 后端 REST API
- `/.well-known/**` → OIDC Discovery/JWKS
- `/register`、`/register/**` → OIDC 动态客户端注册（RFC 7591）

> 请确保后端已启动（见仓库根目录 README：`python main.py start`）。
> SSR 端数据请求不走代理，直连后端，地址由 `runtimeConfig.apiBase` 配置（生产用环境变量 `NUXT_API_BASE` 覆盖）。

### 3. 构建与预览

```bash
npm run build      # 生产构建（.output/，node-server preset）
npm run preview    # 本地预览构建产物
npm run typecheck  # vue-tsc 类型检查
```

## 目录结构

```
frontend/
├── nuxt.config.ts          # Nuxt 配置（模块、代理、SSR 后端地址）
├── tsconfig.json           # extends .nuxt/tsconfig.json（npm install 后自动生成）
└── app/                    # Nuxt 4 源码目录
    ├── app.vue             # 根组件（NuxtLayout + NuxtPage）
    ├── pages/              # 文件路由
    │   ├── login.vue       # 登录（/login）
    │   ├── signup.vue      # 注册（/signup，避让后端 OIDC /register）
    │   ├── index.vue       # 仪表盘（/）
    │   ├── profile.vue     # 个人资料
    │   ├── oauth-apps.vue  # OAuth 应用管理
    │   ├── authorized-apps.vue  # 已授权应用
    │   └── admin/          # 管理后台（概览/用户/客户端/Scope/Webhook）
    ├── layouts/            # default（主布局）/ auth（登录注册布局）
    ├── components/common/  # AppHeader / AppSidebar
    ├── middleware/auth.global.ts  # 全局路由守卫（游客/登录/管理员）
    ├── plugins/
    │   ├── api.ts          # $api 全局 ofetch 实例（Bearer 注入 + 错误处理）
    │   └── element-plus.ts # Element Plus 注册
    ├── stores/             # auth（cookie 化）/ app
    ├── composables/        # useAuth / useAuthApi / useOauthApi(+useConsentApi) / useAdminApi
    ├── types/index.ts      # TS 类型定义
    └── assets/styles/      # Sass 变量与全局样式
```

## 页面路由

| 路径 | 页面 | 权限 |
| --- | --- | --- |
| `/login` | 登录 | 游客 |
| `/signup` | 注册 | 游客 |
| `/` | 仪表盘 | 登录 |
| `/profile` | 个人资料 | 登录 |
| `/oauth-apps` | OAuth 应用（创建/密钥轮换） | 登录 |
| `/authorized-apps` | 已授权应用（撤销同意） | 登录 |
| `/admin` | 管理概览 | 管理员 |
| `/admin/users` | 用户管理 | 管理员 |
| `/admin/clients` | 客户端管理 | 管理员 |
| `/admin/scopes` | Scope 管理 | 管理员 |
| `/admin/webhooks` | Webhook 管理 | 管理员 |

## 说明

- **认证**：`access_token` / `refresh_token` / `user` 存于 cookie（`sameSite: lax`），SSR 与客户端均可读；`$api` 请求拦截自动注入 `Authorization: Bearer`；401 时清除会话并跳转登录页
- **SSR 数据获取**：列表/统计页用 `useAsyncData` 服务端预取（`pending` + `refresh`），登录/注册/表单页保留 `onMounted` 命令式请求
- **管理员判定**：路由守卫按登录用户邮箱（`admin@zerotrust.local`）拦截 `/admin/*`
- **路径约定**：后端 OIDC 动态客户端注册占用根路径 `/register`，前端用户注册页因此使用 `/signup`
- **已知问题**：Windows + Node 22 下 Nitro 依赖追踪（@vercel/nft）有 readlink EISDIR 问题（nuxt/nuxt#20915），已通过 `nitro.externals.trace: false` 绕过（仅影响 `.output` 依赖精简）；建议 Node ≥ 22.18
