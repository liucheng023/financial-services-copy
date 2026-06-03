# FinAgentOS Phase 1 — Tasks

## Foundation

### Task 1: 项目初始化
- [ ] 初始化 FastAPI 后端项目（Python 3.11+）
- [ ] 初始化 React 前端项目（Vite + TypeScript + TailwindCSS + Zustand）
- [ ] 配置 Supabase 项目，创建数据库表（agents, skills, verticals, mcp_servers, agent_skills, agent_mcps, vertical_skills, vertical_mcps, chat_sessions, chat_messages, model_configs）
- [ ] 配置开发环境（.env、docker-compose 可选）
- **Deliverable**: 两个项目可启动，Supabase 表结构就绪

### Task 2: 数据导入脚本
- [ ] 编写 Python 脚本解析 agents/<slug>.md（frontmatter + body 结构化）
- [ ] 编写 SKILL.md 解析器（frontmatter + content）
- [ ] 编写 .mcp.json 解析器
- [ ] 编写 plugin.json 解析器
- [ ] 建立 MCP 工具名映射表（capiq → S&P Global 等）
- [ ] 实现全量导入 API（POST /api/import/all）
- [ ] 实现增量导入 API（agents / verticals / mcps）
- **Deliverable**: 运行导入后 Supabase 有完整的 10 agents + 7 verticals + 50+ skills + 11 MCPs

## Backend Core

### Task 3: Agent/Skills/MCP API
- [ ] GET /api/agents（列表，含 skill_count, mcp_count）
- [ ] GET /api/agents/{slug}（详情，含 skills 列表、mcps 列表、workflow、guardrails）
- [ ] GET /api/verticals（列表）
- [ ] GET /api/verticals/{slug}（详情，含 skills、mcps）
- [ ] GET /api/mcp-servers（列表，含状态）
- [ ] POST /api/mcp-servers（新增）
- [ ] GET /api/mcp-servers/{id}（详情，含工具列表）
- **Deliverable**: 所有只读 API + MCP 新增 API 可用

### Task 4: MCP 适配层
- [ ] 集成 mcp-use 库
- [ ] 实现 OpenAIMCPAdapter 初始化流程（从 Supabase 加载 MCP 配置 → 连接 → 转换工具）
- [ ] 实现 tool call 执行流程（model 返回 tool_calls → adapter.tool_executors 执行 → 结果喂回）
- [ ] 实现 MCP 健康检查端点
- **Deliverable**: MCP 工具可被 OpenAI 兼容模型调用

### Task 5: 对话循环引擎
- [ ] POST /api/sessions（创建会话，加载 Agent prompt + Skills + MCP 工具）
- [ ] POST /api/sessions/{id}/messages（发送消息，SSE 流式响应）
- [ ] 实现 function calling 循环（model → tool_calls → execute → feed back → repeat）
- [ ] 实现上下文窗口管理（system prompt + 历史 + 当前，超长时截断）
- [ ] GET /api/sessions（会话列表）
- [ ] GET /api/sessions/{id}（会话详情 + 消息历史）
- **Deliverable**: 可与 Agent 进行完整对话，MCP 工具调用正常

### Task 6: 模型配置 API
- [ ] GET /api/model-configs（列表）
- [ ] POST /api/model-configs（新增，API key 加密存储）
- [ ] PUT /api/model-configs/{id}（更新）
- [ ] 实现测试连接端点（发送简单消息验证配置）
- [ ] 实现默认模型设置
- **Deliverable**: 可配置 GLM-5 并测试连接

## Frontend

### Task 7: 布局与导航
- [ ] 实现 Sidebar 组件（默认对话、专家、技能包、MCP、聊天记录、系统配置）
- [ ] 实现 Layout 组件（Sidebar + Main）
- [ ] 实现路由（React Router）
- [ ] 实现 Zustand 全局状态（当前会话、当前 Agent、模型配置）
- **Deliverable**: 导航框架可用，各页面可切换

### Task 8: 对话页
- [ ] 实现 ChatPage 组件
- [ ] 实现 AgentSelector（顶部 Agent 切换下拉）
- [ ] 实现 MessageList（用户消息、助手消息、工具调用消息）
- [ ] 实现 ChatInput（输入框 + 发送按钮）
- [ ] 实现 SSE 流式接收和逐 token 渲染
- [ ] 实现 Agent 切换确认对话框
- [ ] 实现 ToolCallMessage（折叠/展开工具调用详情）
- **Deliverable**: 可与 Agent 进行流式对话，工具调用可视化

### Task 9: Agent 列表/详情页
- [ ] 实现 AgentListPage（10 个 Agent 卡片）
- [ ] 实现 AgentDetailPage（角色、工作流、技能、MCP、护栏）
- [ ] 实现"开始对话"按钮（跳转对话页并选择 Agent）
- **Deliverable**: 10 个 Agent 可浏览，详情完整

### Task 10: 技能包列表/详情页
- [ ] 实现 VerticalListPage（7 个技能包卡片）
- [ ] 实现 VerticalDetailPage（Skills 列表、MCP 列表、关联 Agent）
- [ ] 实现 Skill 内容预览（前 500 字符 + 展开全文）
- **Deliverable**: 7 个技能包可浏览，Skill 内容可查看

### Task 11: MCP 管理页
- [ ] 实现 McpListPage（11 个 MCP 卡片，显示状态）
- [ ] 实现 McpDetailPage（工具列表、关联 Agent/Vertical）
- [ ] 实现 McpCreatePage（新增 MCP 表单）
- [ ] 实现测试连接功能
- **Deliverable**: MCP 可浏览、新增、测试连接

### Task 12: 系统配置页
- [ ] 实现 ConfigPage（模型配置列表）
- [ ] 实现模型配置表单（base_url, api_key, model_name, temperature, max_tokens）
- [ ] 实现测试连接功能
- [ ] 实现默认模型设置
- **Deliverable**: 可配置 GLM-5 并设为默认

### Task 13: 聊天记录页
- [ ] 实现 HistoryPage（按时间倒序，可按 Agent 筛选）
- [ ] 实现对话回放视图（完整消息历史，工具调用可折叠）
- [ ] 实现删除功能（单条 + 批量）
- **Deliverable**: 聊天记录可浏览和删除

## Integration & Polish

### Task 14: 端到端集成测试
- [ ] 验证：导入数据 → 配置 GLM-5 → 选择 Pitch Agent → 发送消息 → 收到流式响应
- [ ] 验证：MCP 工具调用在对话中正常工作
- [ ] 验证：Agent 切换功能正常
- [ ] 验证：聊天记录保存和回看正常
- **Deliverable**: 核心流程端到端可运行
