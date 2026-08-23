# Zero Trust OIDC Platform — 零信任用户中台（后端）

基于 FastAPI + SQLModel 的四层 DDD 架构 OIDC 用户中心，内置零信任安全体系：TOTP 双因素认证、设备指纹绑定、风险评估引擎、结构化审计日志、社交账号绑定与验证码异步发送。类 GitHub OAuth Apps，支持第三方系统通过 OAuth 2.0 / OIDC 接入。

## 功能特性

- **OIDC / OAuth 2.0**：授权码 + PKCE、动态客户端注册、Token 签发/吊销/内省、用户同意（Consent）管理、JWKS / Discovery
- **零信任登录**：密码登录 → 风险评估引擎（新设备/新 IP/失败计数/多 IP 切换/异常时段/黑名单）→ ALLOW / CHALLENGE_2FA / BLOCK 三态判定
- **TOTP 双因素认证**：扫码绑定、用户可配置开关、登录第二步挑战
- **设备指纹绑定**：SHA256(IP|UA|Accept-Language|Sec-CH-UA)，设备列表/信任/撤销（撤销连带会话吊销）
- **社交登录**：GitHub / Google / 通用 OAuth2 适配器，账号绑定与解绑
- **验证码体系**：ARQ 异步发送（Redis 不可用自动降级进程内执行）、bcrypt 哈希落库、限流与每日上限
- **审计日志**：结构化事件（登录/2FA/社交/设备/风险/管理员操作），分页 + 多维过滤查询
- **多数据库**：SQLite（默认，零配置）/ PostgreSQL / MySQL 一键切换
- **可观测性**：Prometheus 指标（/metrics）、健康检查、请求 ID 追踪

## 技术栈

| 分类 | 技术 |
| --- | --- |
| Web 框架 | FastAPI 0.115 / Starlette / Uvicorn |
| ORM | SQLModel / SQLAlchemy 2.0（async）+ Alembic 迁移 |
| 数据库 | SQLite（aiosqlite）/ PostgreSQL（asyncpg）/ MySQL（asyncmy） |
| 缓存 | Redis 5（可选，不可用自动降级内存后端） |
| 异步任务 | ARQ（worker 模式 / 进程内降级） |
| 认证 | python-jose（JWT）、bcrypt、pyotp（TOTP） |
| 邮件 | aiosmtplib（未配置 SMTP 时降级日志输出） |
| 监控 | prometheus-client |

## 目录结构（DDD 四层）

```
app/
├── domain/                  # 领域层：纯 Python，零框架依赖
│   ├── identity/            # 身份域：密码策略与哈希
│   ├── security/            # 安全域：TotpService/RiskAssessmentService(规则引擎)/FingerprintService
│   └── federation/          # 联邦域：TokenManager/ClaimsBuilder/PKCE/同意判定
├── application/             # 应用层：用例编排
│   ├── auth_use_cases.py    # 注册/登录(风险+2FA)/刷新/登出/MFA 管理
│   ├── oidc_flow.py         # GrantHandler/OIDCProvider（授权码流程）
│   ├── social_use_cases.py  # 社交绑定与登录
│   ├── verification_use_cases.py  # 验证码请求/校验
│   ├── device_use_cases.py  # 设备列表/信任/撤销
│   ├── risk_use_cases.py    # 风险评估编排与事件查询
│   └── audit_service.py     # 审计写入与查询
├── infrastructure/          # 基础设施层
│   ├── config/              # 环境配置（App/Database/Redis/Cors/Mail/Security）
│   ├── database.py          # DatabaseManager（多引擎适配）
│   ├── persistence/
│   │   ├── models/          # SQLModel 表模型
│   │   └── repositories/    # SqlAuditRepository（实现领域接口）
│   ├── cache/backend.py     # CacheBackend ABC → Redis/Memory 双后端
│   ├── messaging/           # ARQ：worker/tasks/dispatcher（优雅降级）
│   ├── mail/mailer.py       # SMTP 发送（未配置→日志降级）
│   └── social/              # 社交适配器：github/google/generic + registry
└── interface/               # 接口层
    ├── api/
    │   ├── endpoints/       # REST 端点（auth/mfa/social/verification/devices/consent/user/oidc/admin）
    │   ├── schemas/         # Pydantic 请求/响应模型
    │   └── deps/            # 依赖注入（token 解析/当前用户）
    └── middlewares/         # 安全头/限流/Prometheus/异常处理
```

## 快速开始

### 1. 环境准备

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows；Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置

复制 `.env` 并调整（默认 SQLite 零配置即可运行）：

```ini
APP_NAME=user_platform
SECRET_KEY=your-secret-key        # JWT 签名密钥，生产环境务必更换

# 数据库引擎：sqlite+aiosqlite（默认） / postgresql+asyncpg / mysql+asyncmy
DB_ENGINE=sqlite+aiosqlite
DB_DATABASE=user_platform.db

# Redis（可选，不可用时缓存/任务自动降级）
REDIS_HOST=127.0.0.1
REDIS_PORT=6379

# SMTP 邮件（未配置时验证码邮件降级为日志输出）
SMTP_HOST=
SMTP_FROM=

# 风险引擎：高风险 IP 黑名单（逗号分隔，命中 +50 分直接 BLOCK）
RISK_IP_BLACKLIST=
```

### 3. 数据库迁移与启动

```bash
# 生成/应用迁移（新模型：VerificationCode/RiskEvent/AuthorizationCode 等）
python main.py db revision -m "init"
python main.py db migrate

# 启动服务（默认 0.0.0.0:8000，热重载开启）
python main.py start

# 或直接 uvicorn
uvicorn main:app --reload

# 启动 ARQ 后台 worker（生产模式，需 Redis；无 Redis 时任务自动进程内执行）
python main.py worker
```

### 4. 验证

- 健康检查：`GET /healthy`
- 接口文档：`http://localhost:8000/docs`（Swagger）/ `/redoc`
- 监控指标：`GET /metrics`

## CLI 命令

| 命令 | 说明 |
| --- | --- |
| `python main.py start [--host H] [--port P] [--no-reload]` | 启动 HTTP 服务 |
| `python main.py worker [--max-jobs N]` | 启动 ARQ 后台任务 worker |
| `python main.py db revision -m "msg"` | 生成迁移版本（autogenerate） |
| `python main.py db migrate [-v heads]` | 应用迁移 |
| `python main.py db downgrade [--steps N]` | 回滚迁移 |

## API 端点概览

### 认证与安全（`/api/v1`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/auth/register` | 注册（可选邮箱验证码） |
| POST | `/auth/login` | 登录（风险引擎 → 2FA/TOTP/邮箱验证码挑战 → 签发令牌） |
| POST | `/auth/login/mfa` | 登录第二步（挑战令牌 + TOTP/验证码） |
| POST | `/auth/logout` | 登出（撤销当前会话） |
| POST | `/auth/refresh` | 刷新令牌 |
| PUT | `/auth/change-password` | 修改密码（强度校验 + 审计） |
| POST | `/auth/mfa/totp/setup` | 初始化 TOTP 绑定（返回 secret + otpauth URI） |
| POST | `/auth/mfa/totp/confirm` | 校验动态码后启用 TOTP |
| GET | `/auth/mfa/status` | 查询 MFA 开关状态 |
| DELETE | `/auth/mfa` | 禁用 MFA（需密码或 TOTP） |
| GET | `/auth/social/{provider}/authorize` | 社交授权跳转（provider: github/google/generic） |
| GET | `/auth/social/{provider}/callback` | 社交回调（登录/绑定/自动注册） |
| GET | `/auth/social/accounts` | 我的社交绑定列表 |
| DELETE | `/auth/social/{account_id}` | 解绑社交账号 |
| POST | `/verification/request` | 请求验证码（60s 限流 + 每日上限，异步发送） |
| POST | `/verification/verify` | 校验验证码（email_verify/2fa_backup/risk_challenge） |
| GET | `/devices` | 我的设备列表（标记当前设备） |
| POST | `/devices/{id}/trust` | 信任设备（信任分提升至 0.8） |
| DELETE | `/devices/{id}` | 撤销设备 + 吊销其所有活跃会话 |
| GET | `/user` | 个人资料 |
| GET | `/consent` | 我的授权同意列表 |
| DELETE | `/consent/{consent_id}` | 撤销单条授权同意 |
| DELETE | `/consent/client/{client_id}` | 撤销某客户端全部同意 |

### OIDC（根路径，无 /api 前缀）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/.well-known/openid-configuration` | OIDC Discovery |
| GET | `/.well-known/jwks.json` | JWKS 公钥集 |
| GET | `/authorize` | 授权端点（authorization_code + PKCE） |
| POST | `/token` | 令牌端点（授权码/刷新） |
| POST | `/token/revoke` | 令牌吊销 |
| POST | `/token/introspect` | 令牌内省 |
| GET | `/userinfo` | 用户信息端点 |
| POST | `/register` | 动态客户端注册（RFC 7591） |
| GET | `/register/{client_id}` | 查询客户端注册信息 |
| POST | `/register/{client_id}/rotate-secret` | 轮换客户端密钥 |

### 管理员（`/api/admin`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/PUT/DELETE | `/users*` | 用户管理（列表/详情/启用停用/编辑/重置密码/删除） |
| GET/PUT | `/clients*` | OAuth 客户端管理（列表/详情/审核/启停） |
| GET/POST/DELETE | `/scopes` | Scope 管理 |
| GET/POST/PUT/DELETE | `/providers*` | 社交平台配置（client_id/secret 加密存储） |
| GET | `/audit` | 审计日志查询（action/user/时间段过滤 + 分页） |
| GET/POST | `/webhooks` | Webhook 管理 |
| GET | `/rate-limit/status` | 限流状态 |

## 零信任安全体系

1. **风险评估引擎**（`domain/security/services.py` 纯规则引擎）：
   - 规则：新设备 +30 / 新 IP +20 / 失败 ≥3 次 +30 / 24h 多 IP 切换 +25 / 异常时段(0-5点) +15 / 黑名单 IP +50
   - 判定：< 40 放行；40-70 挑战（TOTP 或邮箱验证码）；> 70 拒绝并审计
   - 每次评估落库 `RiskEvent`（评分/命中规则/动作），登录成功自动清除失败计数
2. **TOTP 双因素**：pyotp 生成/校验，密钥 Fernet 加密存储，登录第二步挑战
3. **设备指纹**：登录自动记录/更新设备，信任分与风险引擎联动，撤销设备连带会话吊销
4. **审计日志**：认证/安全/设备/管理员操作全链路结构化落库

## Redis 优雅降级

Redis 不可用时系统自动降级，功能不中断：

| 能力 | Redis 可用 | Redis 不可用 |
| --- | --- | --- |
| 缓存/限流计数 | RedisBackend | MemoryBackend（进程内 dict + 过期清理） |
| 验证码发送 | ARQ 队列 | 进程内 `asyncio.create_task` 直接执行 |
| OAuth 授权码 | —（已彻底迁入 DB，10 分钟过期） | 同左 |
| 启动行为 | 正常 | 仅告警，不阻断启动 |

## 测试

```bash
# 冒烟路径：注册 → 登录（风险/2FA 挑战）→ TOTP 绑定 → 设备信任/撤销
#          社交授权 URL → 验证码请求（日志模式）→ 管理员审计查询
pytest            # 单元测试
```

## License

MIT
