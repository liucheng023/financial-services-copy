# mcp-management Spec

## ADDED Requirements

### Requirement: MCP 服务器列表页
- The page SHALL display all MCP 服务器的卡片列表
- Each card SHALL show：名称、URL（脱敏）、状态（已配置/未连接）

#### Scenario: 浏览 MCP 列表
Given 数据已导入 Supabase
When 用户访问 MCP 页面
Then 显示 11 个 MCP 服务器卡片，Daloopa 显示为"已配置"

### Requirement: MCP 详情页
- The detail page SHALL display:名称、URL、描述、关联的 Vertical、关联的 Agent
- 显示该 MCP 服务器提供的工具列表

#### Scenario: 查看 Daloopa MCP 详情
Given 用户点击 Daloopa MCP
Then 详情页显示 URL、关联的 financial-analysis 垂直包、使用 Daloopa 的 Agent 列表
And 显示 Daloopa MCP 提供的工具列表

### Requirement: 新增 MCP
- Form fields SHALL include：名称（必填）、URL（必填）、API Key（选填）、描述（选填）
- After submission, the system SHALL attempt连接，成功标记"已配置"，失败保存但标记"未连接"

#### Scenario: 新增 MCP 服务器
Given 用户点击新增 MCP
When 用户填写名称"Custom Data"、URL"https://mcp.example.com/mcp"并提交
Then 系统尝试连接，连接成功标记为"已配置"，失败标记为"未连接"但保存配置

### Requirement: MCP 健康检查
- The system SHALL support a manual"测试连接"按钮
- Test results SHALL show：成功（显示工具数量）/ 失败（显示错误信息）

#### Scenario: 测试 MCP 连接
Given 用户在 MCP 列表页
When 用户点击 Daloopa 的"测试连接"按钮
Then 系统尝试连接 MCP 服务器，成功显示"连接正常，提供 X 个工具"，失败显示错误信息
