# vertical-management Spec

## ADDED Requirements

### Requirement: 技能包列表页
- The page SHALL display all 7 个垂直技能包的卡片列表
- Each card SHALL show：名称、描述、包含的 Skills 数量、连接的 MCP 数量

#### Scenario: 浏览技能包列表
Given 数据已导入 Supabase
When 用户访问技能包页面
Then 显示 7 个技能包卡片，financial-analysis 显示包含技能数最多和 11 个 MCP

### Requirement: 技能包详情页
- The detail page SHALL display:描述、包含的 Skills 列表、连接的 MCP、关联的 Agent
- 点击 Skill 名称可展开查看内容摘要

#### Scenario: 查看 financial-analysis 技能包详情
Given 用户点击 financial-analysis
Then 详情页显示该包包含的所有 Skills 和 11 个 MCP 连接器
And 显示哪些 Agent 使用了此包的 Skills

### Requirement: Skill 内容预览
- Clicking a Skill SHALL show the first 500 characters of SKILL.md as a summary
- Full content SHALL be expandable via a "View full content" button

#### Scenario: 预览 comps-analysis Skill
Given 用户在 financial-analysis 详情页
When 用户点击 comps-analysis
Then 显示 SKILL.md 的前 500 字符摘要
And "查看完整内容"按钮可展开完整内容
