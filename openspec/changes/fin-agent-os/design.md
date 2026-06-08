## Context

Anthropic 的 financial-services 项目是一个纯 markdown/JSON/YAML 内容仓库（39,893 行 markdown，0 行业务代码），包含 10 个金融 Agent、7 个垂直技能包、50+ 个技能和 11 个 MCP 数据连接器。当前只能通过 Claude Cowork 或 Managed Agent API 使用，且锁定 Claude 模型。

我们的目标是构建金融版 Omniwork.ai——一个模型无关的金融 Agent OS。Phase 1 聚焦基础平台：Agent 对话 + 专家市场 + MCP 管理 + 模型配置。

关键技术约束：
- 39,893 行 markdown 提示词不能重写，必须原样复用
- MCP → Function Calling 适配是模型无关的核心
- 项目文件是导入源（只读），Supabase 是运行时数据源

## Goals / Non-Goals

**Goals:**
- 10 个 Agent 在 Web UI 可见，2-3 个可实际对话
- MCP 连接器可配置，至少 1 个可实际调用
- 支持 OpenAI 兼容格式接入任意模型（GLM-5 优先）
- 对话中切换 Agent，加载对应的 prompt + skills + MCP
- 聊天记录持久化，可回看
- 为 Phase 2（多 Agent 协作）和 Phase 3（记忆系统）预留架构空间

**Non-Goals:**
- 不修改原始 financial-services 项目的任何文件
- 不实现多 Agent 协作（Phase 2）
- 不实现记忆系统或周期性自动化（Phase 3）
- 不实现 Agent/技能包的新增表单（P2 阶段）
- 不实现端到端用户认证（Phase 1 为内部工具，写接口用 admin token 保护；Phase 2 引入 Supabase Auth）
- 不处理 Agent 生成文件（Excel/PPTX）的在线预览（仅提供下载）

## Decisions

### Decision 1: 技术栈选择

**选择: Next.js (App Router) + FastAPI + Supabase + mcp-use**

| 选项 | 优势 | 劣势 |
|---|---|---|
| **Next.js + FastAPI + Supabase**（选定） | Python MCP 生态 + Next.js 未来 SSR/SEO 不卡壳 + Vercel 原生部署 | 两个运行时 |
| Vite SPA + FastAPI + Supabase | 前端更简单 | 未来要 SSR 需重写为 Next.js（1-2 周成本） |
| Next.js 全栈 + Supabase | 前后端统一 TypeScript | MCP 适配库 Python 生态更成熟，TS 生态弱 |

**理由**:
- **前端 Next.js**: 当前是 B2B chat UI 主导，几乎全是 Client Component，Next.js 开发体验和 Vite SPA 接近。但 1-2 个月后如果需要 SSR/SEO（Agent 详情页被搜索引擎收录），不需要重写
- **后端 FastAPI**: Python 生态的 MCP 适配库最成熟（mcp-use 的 OpenAIMCPAdapter），async 支持适合对话流式输出
- **前后端分离**: 各自独立部署、独立扩展、独立技术演进

### Decision 1.5: 部署架构

**前端: Vercel**
- Next.js 原生支持，零配置部署
- 全球 CDN，静态资源访问快
- 自动 HTTPS、自动预览部署

**后端: Fly.io（东京单区域起步）**

| 部署平台 | 关键考量 | 评估 |
|---|---|---|
| **Fly.io（选定）** | 东京/香港/新加坡节点 + 一键部署 + Docker 化 + 未来私有化友好 | 亚洲 B2B 场景最优 |
| Railway | 一键部署体验好，但只有美国节点 | 亚洲用户延迟 150-200ms |
| Render | 类似 Railway，免费版有冷启动 | 亚洲延迟问题相同 |
| 国内云（阿里云/腾讯云） | 国内访问最快，合规友好 | 部署体验差，对日本/新加坡客户无优势 |

**理由**:
- **B2B 大客户 + 亚洲为主**: 用户在日本/新加坡/香港 + 国内，Fly.io 的东京节点延迟最低
- **流式 chat 体验**: 后端到用户的 SSE 流式输出延迟越低越好
- **未来扩展**: 多区域只需 `fly regions add iad` 一条命令
- **私有化部署**: 大客户要求 on-premise 时，Docker 镜像直接交付
- **MCP 调用慢可接受**: 后端到 MCP 服务器（美国）的延迟用户感受不到，仅增加总响应时间

### Decision 1.6: 工程目录结构

新建独立目录 `2033_fin_agent/`，与原 financial-services 内容仓库分离：

```
2033_fin_agent/
├── AGENTS.md                    # 项目级规范
├── README.md
├── backend/
│   ├── AGENTS.md                # 后端规范
│   ├── app/
│   │   ├── api/                 # FastAPI 路由
│   │   ├── core/                # 配置、依赖
│   │   ├── services/            # 业务逻辑
│   │   ├── adapters/            # MCP 适配层
│   │   └── importers/           # 数据导入脚本
│   ├── tests/
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── fly.toml
├── frontend/
│   ├── AGENTS.md                # 前端规范
│   ├── app/                     # Next.js App Router
│   ├── components/
│   ├── lib/                     # API client, utils
│   ├── stores/                  # Zustand stores
│   ├── package.json
│   └── next.config.js
└── docs/
    └── architecture.md
```

**理由**: 原仓库是 markdown/JSON 内容仓库（39K 行 markdown），不应混入代码工程。新工程独立目录，原仓库作为数据源（导入脚本读它的 markdown 文件）。

### Decision 2: MCP 适配层

**选择: mcp-use OpenAIMCPAdapter**

**理由**: 搜索发现已有成熟方案：
- `mcp-use`（Python）：OpenAIMCPAdapter 直接将 MCP 工具转为 OpenAI function calling 格式
- `mcp-function-calling-adapter`（TypeScript）：功能类似但生态较小
- `mcpkit`：多协议网关，过度设计

mcp-use 的适配流程：
1. 从 Supabase 加载 Agent 关联的 MCP 服务器配置
2. 初始化 MCPClient 连接各 MCP 服务器
3. OpenAIMCPAdapter.create_all() 转换工具为 function schema
4. 模型返回 tool_calls → adapter.tool_executors 执行 → 结果喂回模型

### Decision 3: Agent Prompt 适配策略

**选择: 分层注入**

Agent 的 system prompt 由三层组成：
1. **角色层**: 从 `agents/<slug>.md` 解析，作为 system message 主体
2. **技能层**: 从 agent 关联的 skills 目录读取 SKILL.md，拼接到 system message 末尾
3. **工具层**: 由 mcp-use 自动从 MCP 服务器发现并转换为 function schema

原始 prompt 中的 `tools: Read, Write, Edit, mcp__capiq__*` 不需要手动修改——mcp-use 的 adapter 会自动处理工具发现和转换。

**Skills 注入策略**: Phase 1 采用全量注入（所有关联 skills 拼接到 system prompt）。如果 token 开销过大（某些 Agent 有 10+ 个 skills，每个 100-600 行），Phase 2 可切换为按需检索（RAG）。

### Decision 4: 数据流

**选择: 项目文件 → 导入脚本 → Supabase → 运行时**

```
导入阶段（一次性 + 增量）:
  markdown/YAML/JSON 文件 → Python 解析脚本 → Supabase

运行时:
  Web 前端 → FastAPI API → Supabase (读 Agent/Skills/MCP 配置)
                           → mcp-use (MCP 适配)
                           → OpenAI SDK (模型调用)
                           → Supabase (写对话记录)
```

项目文件是 source of truth 的导入源，不是运行时数据源。这允许：
- 运行时完全依赖 Supabase，不需要读文件系统
- 修改 Supabase 中的配置不影响原始项目文件
- 未来支持用户在 UI 中修改 Agent 配置（Phase 2+）

### Decision 5: 前端架构

**选择: Next.js 14 (App Router) + TypeScript + TailwindCSS + shadcn/ui + TanStack Query + Zustand + pnpm**

这是 Decision 1 的具体前端展开。对标 Vercel AI Chatbot 模板 + Vercel AI SDK 数据流协议。

页面结构（Next.js App Router）：
```
app/
├── layout.tsx                   # Root layout (Sidebar + Main)
├── page.tsx                     # Home → redirect to /agents
├── agents/
│   ├── page.tsx                 # Agent marketplace (10 cards)
│   └── [slug]/
│       ├── page.tsx             # Agent detail (role, workflow, skills, MCPs, guardrails)
│       └── chat/
│           └── page.tsx         # Chat with this agent
├── verticals/page.tsx           # Vertical list
├── mcp-servers/page.tsx         # MCP management
├── history/page.tsx             # Chat history
└── admin/
    └── settings/page.tsx        # Model config + admin token entry (internal operator-only tool, see Decision 7)
```

对话页面组件：
```
ChatPage (client component)
├── AgentSelector (顶部 Agent 切换)
├── MessageList (消息列表，支持流式输出)
│   ├── UserMessage
│   ├── AssistantMessage
│   ├── ToolCallMessage (MCP 工具调用展示)
│   └── SystemMessage
├── ChatInput (输入框 + 发送)
└── AgentInfoPanel (当前 Agent 信息侧栏)
```

流式接收：使用 `fetch` + `ReadableStream` 解析 SSE（非原生 `EventSource`，因为聊天端点是 POST）。

Auth: Phase 1 无端用户认证。Admin/operator-only 页面通过 `X-Admin-Token` 请求头调用受保护写端点。详见 Decision 7。`INTERNAL_ADMIN_TOKEN` 是 Phase 1 临时的内部 operator/admin API guard，不是用户认证机制，禁止用于公开端用户界面。Phase 2 改用 Supabase Auth + RBAC + RLS。

### Decision 6: 后端 API 设计

```
# Agent
GET    /api/agents              # Agent 列表
GET    /api/agents/{slug}       # Agent 详情（含 skills、mcps）

# Verticals
GET    /api/verticals           # 技能包列表
GET    /api/verticals/{slug}    # 技能包详情（含 skills、mcps）

# MCP
GET    /api/mcp-servers         # MCP 列表
POST   /api/mcp-servers         # 新增 MCP
GET    /api/mcp-servers/{id}    # MCP 详情
PUT    /api/mcp-servers/{id}    # 更新 MCP

# 对话
POST   /api/sessions            # 创建对话（指定 agent_id）
POST   /api/sessions/{id}/messages  # 发送消息（SSE 流式响应）
GET    /api/sessions             # 对话列表
GET    /api/sessions/{id}       # 对话详情（含消息历史）

# 配置
GET    /api/model-configs       # 模型配置列表
POST   /api/model-configs       # 新增配置
PUT    /api/model-configs/{id}  # 更新配置

# 导入
POST   /api/import/all          # 从项目文件全量导入
POST   /api/import/agents       # 仅导入 Agents
POST   /api/import/verticals    # 仅导入技能包
POST   /api/import/mcps         # 仅导入 MCP 配置
```

所有写端点（POST/PUT/DELETE on `/api/import/*`, `/api/mcp-servers`, `/api/model-configs`）需要请求头 `X-Admin-Token: <INTERNAL_ADMIN_TOKEN>`。读端点 + 聊天端点公开。

### Decision 7: Auth 策略（Phase 1）

**选择: 内部 admin token 保护写端点，读+聊天端点公开，不做端到端用户认证**

| 维度 | Phase 1 决策 | Phase 2 演进 |
|---|---|---|
| 用户登录 | 无 | Supabase Auth (邮箱/SSO) |
| Session 归属 | 匿名（user_id 列为 nullable，留空） | user_id 绑定登录用户 |
| 读端点 | 公开 | 公开 |
| 写端点 | `X-Admin-Token` 头 | 管理员角色 (RBAC) |
| 聊天端点 | 公开匿名 | 绑定用户 + RLS |
| 多租户 | 无 | 工作区 (workspaces) + RLS |

**理由**:
- Phase 1 是内部 MVP，做完整 auth 拖慢交付且会因 Supabase Auth 集成踩坑
- admin token 足够阻挡误操作（重新导入、修改 MCP 配置）
- `chat_sessions` 表 schema 必须包含 `user_id UUID NULL`，Phase 2 才能无痛迁移

**`INTERNAL_ADMIN_TOKEN` 契约（明确边界，防止被误解为用户认证）**：

1. **Phase 1 only.** Phase 2 切到 Supabase Auth 时 `require_admin_token` 和该 env 一并删除。
2. **内部 operator/admin API guard。** 不是用户认证机制，不携带用户身份。
3. **Server-side 部署 secret。** 本地放 `backend/.env`，生产用 Fly.io secrets（或同类 secret manager），仅以 out-of-band 渠道分发给运维人员。
4. **不是 OAuth / 不是 JWT / 不是 session token / 不是 RBAC。** 单一共享 bearer-style 密钥。
5. **不可暴露给普通端用户客户端。** 公开 marketplace、Agent 详情页、聊天页绝不能持有该 token。
6. **不可被普通端用户前端长期持有。** Phase 1 的 admin/settings 页面（`/admin/settings`）若让运维粘贴 token 并临时缓存于 `localStorage`，**仅作为 internal operator/MVP dev convenience**，限制条件：
   - 必须以 operator-only internal tool 文档化（路由不上 sitemap，不出现在公开导航）
   - 不能用作生产公开用户环境的认证入口
   - 部署可见性限制（例如 Vercel preview / 仅内网可达 / 路由级 robots noindex），不可作为公开可达页面
   - 更长期/合规化方案：Phase 2 改为 Supabase Auth + admin role + RLS 后，此页面整体替换为受 admin role 保护的真正后台
7. **Phase 2 替换。** Supabase Auth (`Authorization: Bearer <JWT>`) + 角色/RBAC + Postgres RLS。

### Decision 8: SSE 事件协议

**选择: 仿 Vercel AI SDK data-stream 风格，事件名按 chat lifecycle 命名**

`POST /api/sessions/{id}/messages` 返回 `text/event-stream`，事件顺序：

```
message_start  → token* → (tool_call → tool_result)* → token* → message_complete → done
                                                                                     │
                                  any time on failure:  error → done ────────────────┘
```

事件 schema（data 段都是 JSON）：

| event | data |
|---|---|
| `message_start` | `{message_id, session_id}` |
| `token` | `{delta: string}` |
| `tool_call` | `{tool_call_id, tool, args}` |
| `tool_result` | `{tool_call_id, result, is_error}` |
| `message_complete` | `{message_id, finish_reason}` |
| `error` | `{code, message, recoverable}` |
| `done` | `{}`（永远最后一个，连接关闭） |

**规则**:
- 用户消息在 stream 启动前已 persisted（HTTP 200 一旦写头就不再变状态码）
- 流中错误用 `error` 事件 + `done` 结束，不用 HTTP 错误码
- `tool_call` 可并发多次，frontend 用 `tool_call_id` 配对 `tool_result`
- 错误响应（4xx/5xx）只发生在流尚未启动前（如 session 不存在），body 是 RFC 7807 problem details JSON：
  ```json
  {"type": "about:blank", "title": "Session not found", "status": 404, "code": "session_not_found", "detail": "ses_xxx does not exist"}
  ```

### Decision 9: Upstream 路径配置

**选择: 全部通过 `UPSTREAM_PLUGINS_PATH` env var 读取，禁止硬编码**

- 本地开发：将 `UPSTREAM_PLUGINS_PATH` 指向本机克隆的上游 `anthropics/financial-services` 仓库下的 `plugins/` 目录
- CI/容器：mount 后通过 env 注入

Importer 脚本 (`backend/app/importers/`) 只读上游，禁止 write。这允许 dev 在不同机器、不同 clone 路径都能跑。

## Risks / Trade-offs

**[Skills 全量注入导致 token 开销过大]** → Phase 1 先做，监控实际 token 消耗。如果单次对话 system prompt 超过 10K tokens，Phase 2 切换为按需检索（RAG）。

**[MCP 服务器需要付费 API key]** → Phase 1 只配置免费或已可用的 MCP。UI 上明确标注哪些 MCP 需要 API key，未配置的标记为"未连接"。

**[GLM-5 的 function calling 兼容性]** → 先用 OpenAI SDK 的标准 function calling 格式，如果 GLM-5 不兼容，需要适配层转换。风险可控——大多数国产模型已兼容 OpenAI 格式。

**[项目文件与 Supabase 数据不同步]** → 提供 `/api/import/all` 端点手动触发重新导入。未来可加 webhook 或文件监控自动同步。

**[Agent prompt 中 `mcp__capiq__*` 格式的工具名与实际 MCP 工具名不匹配]** → 需要映射层。项目的 MCP 服务器名（capiq → S&P Kensho）与 agent frontmatter 中的引用名不一致，导入时需要建立映射表。

## Open Questions

1. **默认对话模式**: 无 Agent 的通用模式下，system prompt 是什么？空白还是有基础指令？
2. **文件产出展示**: Agent 生成 Excel/PPTX 后，前端如何处理？下载链接还是在线预览？
3. **MCP 工具名映射**: agent frontmatter 中的 `mcp__capiq__*` 与实际 MCP 服务器的工具名如何映射？
4. **并发 MCP 调用**: 多个 MCP 工具调用时是否支持并行？

（已决：流式输出 → Decision 8 选定逐 token + SSE 事件协议；认证 → Decision 7 选定 admin token + Phase 2 演进）
