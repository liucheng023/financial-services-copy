# agent-chat Spec

## ADDED Requirements

### Requirement: 对话会话创建
- The system SHALL allow users to选择一个 Agent 创建对话会话
- When creating a session, the system SHALL，后端加载该 Agent 的 system prompt + 关联 Skills 知识 + 关联 MCP 工具
- The system prompt SHALL consist of 由角色层（agent prompt）+ 技能层（skills 内容）组成
- If no Agent is selected, the system SHALL Agent，创建通用对话会话（system prompt 为空或基础指令）

#### Scenario: 用户选择 Pitch Agent 创建对话
Given 用户在对话页点击 Agent 选择器
When 用户选择 "Pitch Agent"
Then 后端加载 pitch-agent.md 作为 system prompt 主体，拼接 11 个 Skills 知识，初始化 CapIQ MCP 工具，创建新会话并返回 session_id

#### Scenario: 用户创建无 Agent 的通用对话
Given 用户未选择任何 Agent
When 用户开始新对话
Then 后端创建空 system prompt 的会话，不加载任何 Skills 或 MCP 工具

### Requirement: 消息发送与响应
- After the user sends a message, the system SHALL，后端构造完整的 messages 数组（system + 历史 + 当前）
- The system SHALL call the OpenAI-compatible 兼容 API 获取响应
- Responses SHALL be returned via SSE 流式返回前端

#### Scenario: 用户发送消息并收到流式响应
Given 用户已创建对话会话
When 用户输入"帮我做 AAPL 的 comps 分析"并发送
Then 后端构造 messages 数组，调用模型 API，通过 SSE 逐 token 流式返回响应

### Requirement: Function Calling 循环
- When the model returns tool_calls, the system SHALL tool_calls 时，后端通过 mcp-use 的 tool_executors 执行 MCP 工具
- Tool execution results SHALL be作为 tool message 喂回模型
- The loop SHALL continue until模型不再调用工具，返回最终文本响应

#### Scenario: 模型调用 MCP 工具获取数据
Given 用户与 Pitch Agent 对话
When 模型返回 tool_calls 请求 CapIQ 数据
Then 后端通过 mcp-use 执行 MCP 工具，将结果喂回模型，模型基于数据生成最终响应

### Requirement: Agent 切换
- The system SHALL allow users to在对话中切换 Agent
- Switching agents SHALL trigger a confirmation dialog确认
- After confirmation, the system SHALL create，加载新 Agent 的 prompt + skills + MCP

#### Scenario: 用户从 Pitch Agent 切换到 GL Reconciler
Given 用户当前与 Pitch Agent 对话
When 用户选择切换到 GL Reconciler
Then 弹出确认对话框，确认后创建新会话，加载 GL Reconciler 的 prompt + skills + MCP，历史会话保存

### Requirement: MCP 工具调用展示
- The frontend SHALL display模型发起的 tool call（工具名 + 参数）
- Tool execution results SHALL be displayed（截断过长内容）
- The system SHALL support collapsible/展开工具调用详情

#### Scenario: 对话中展示 MCP 工具调用
Given 模型调用了 CapIQ 的 get_trading_multiples 工具
When 工具执行完成
Then 前端显示工具调用卡片（工具名 + 参数摘要），可折叠查看完整结果
