# agent-marketplace Spec

## ADDED Requirements

### Requirement: Agent 列表页
- The page SHALL display all 10 个 Agent 的卡片列表
- Each card SHALL show：名称、描述、使用的技能数量、连接的 MCP 数量
- Clicking a card SHALL navigate进入 Agent 详情页

#### Scenario: 浏览 Agent 列表
Given 数据已导入 Supabase
When 用户访问专家页面
Then 显示 10 个 Agent 卡片，每个显示名称、描述、技能数、MCP 数

### Requirement: Agent 详情页
- The detail page SHALL display:角色描述、工作流步骤、产出物、使用的技能列表、连接的 MCP、安全护栏
- The detail page SHALL provide"开始对话"按钮

#### Scenario: 查看 Pitch Agent 详情
Given 用户在 Agent 列表页点击 Pitch Agent
Then 详情页显示角色描述、9 步工作流、2 个产出物、11 个 Skills、1 个 MCP（CapIQ）、3 条护栏
And "开始对话"按钮可点击

#### Scenario: 从详情页开始对话
Given 用户在 Pitch Agent 详情页
When 用户点击"开始对话"
Then 跳转到对话页，自动选择 Pitch Agent

### Requirement: Agent 状态标识
- Agents with configured MCPs SHALL be marked 且可用的 Agent 标记为"可用"
- Agents without configured MCPs SHALL be marked的 Agent 标记为"部分可用"

#### Scenario: Agent 状态显示
Given Pitch Agent 关联的 CapIQ MCP 已配置
When 用户浏览 Agent 列表
Then Pitch Agent 显示为"可用"
