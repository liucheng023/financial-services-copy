## Why

Anthropic 的 financial-services 项目提供了 10 个金融 Agent、7 个垂直技能包、50+ 个技能和 11 个 MCP 数据连接器，但只能通过 Claude Cowork 或 Managed Agent API 两种方式使用。我们需要构建第三个交付渠道——Web 可视化后台，最终目标是打造金融版 Omniwork.ai：一个模型无关的金融 Agent OS，让任何用户通过浏览器与金融专家 Agent 对话完成实际工作任务。

## What Changes

- 新增 Web 前端应用（React + TypeScript），包含对话页、Agent 列表/详情、技能包列表/详情、MCP 管理、系统配置、聊天记录等页面
- 新增后端 API 服务（FastAPI），负责 Agent/Skills/MCP 的加载、对话循环管理、MCP 适配、数据持久化
- 新增 MCP 适配层，使用 mcp-use 将 MCP 工具转换为 OpenAI function calling 格式，实现模型无关的工具调用
- 新增 Supabase 数据模型，存储 Agent 配置、技能包、Skills、MCP 服务器、对话记录、模型配置
- 新增数据导入流程，从项目 markdown/YAML/JSON 文件解析内容到 Supabase
- **BREAKING**: Agent prompt 中的 `tools: Read, Write, Edit, mcp__capiq__*` 格式需要通过适配层转换，原始文件不修改

## Capabilities

### New Capabilities

- `agent-chat`: Agent 对话系统——加载 Agent system prompt + Skills 知识，通过 OpenAI 兼容 API 进行对话，支持 function calling 和 MCP 工具执行
- `agent-marketplace`: Agent 专家市场——展示 10 个金融 Agent，详情页包含角色描述、工作流步骤、产出物、使用的技能、连接的 MCP、安全护栏
- `vertical-management`: 技能包管理——展示 7 个垂直技能包及其包含的 Skills 和 MCP 连接
- `mcp-management`: MCP 连接器管理——展示 11 个 MCP 服务器，支持新增（name + URL + API key）
- `model-config`: 模型配置管理——OpenAI 兼容格式的模型配置（base_url、api_key、model_name），支持 GLM-5 等任意模型
- `chat-history`: 聊天记录管理——按 Agent 分类的对话历史，支持回看
- `data-import`: 数据导入——从项目 markdown/YAML/JSON 解析 Agent、Skills、Vertical、MCP 配置到 Supabase

### Modified Capabilities

（无——这是全新项目，不修改现有 financial-services 项目的任何文件）

## Impact

- **新增代码**: 全新的 Web 应用（前端 + 后端），与现有 financial-services 项目独立
- **依赖**: FastAPI、React、Supabase、mcp-use、OpenAI SDK
- **数据源**: 现有项目的 markdown/YAML/JSON 文件作为导入源（只读）
- **基础设施**: Supabase 实例（Postgres + Storage）
- **MCP 服务器**: 依赖外部金融数据终端的可用性（Daloopa、FactSet 等需要订阅/API key）
