# data-import Spec

## ADDED Requirements

### Requirement: 全量导入
- The system SHALL parse all data from project markdown markdown/YAML/JSON 文件解析所有数据导入 Supabase
- The import scope SHALL cover：agents、skills、verticals、mcp_servers 及其关联关系
- Target tables SHALL be cleared before import目标表

#### Scenario: 首次全量导入
Given Supabase 表为空
When 调用 POST /api/import/all
Then Supabase 中有 10 个 agents、7 个 verticals、50+ skills、11 个 mcp_servers
And 返回统计信息："导入完成：10 agents, 7 verticals, 52 skills, 11 mcp_servers"

### Requirement: Agent Markdown 解析
The system SHALL parse agents/<slug>.md 的 YAML frontmatter（name, description, tools）
- The system SHALL parse the markdown body 中的关键段落（Workflow, Guardrails, Skills this agent uses 等）
- Parsed data SHALL be stored structurally in agents 表

#### Scenario: 解析 Pitch Agent
Given pitch-agent.md 存在
When 导入脚本解析该文件
Then agents 表新增一行：name="pitch-agent", workflow 包含 9 个步骤, guardrails 包含 3 条护栏, skills 关联 11 个 Skill

### Requirement: SKILL.md 解析
The system SHALL parse SKILL.md 的 YAML frontmatter（name, description）
- Data SHALL be stored in the skills table 表，关联到 vertical_id
- The content field SHALL store存储完整 SKILL.md 内容

#### Scenario: 解析 comps-analysis Skill
Given financial-analysis/skills/comps-analysis/SKILL.md 存在（661 行）
When 导入脚本解析该文件
Then skills 表新增一行：name="comps-analysis", vertical_id 指向 financial-analysis, content 包含完整 661 行

### Requirement: MCP 工具名映射
- The system SHALL establish a mapping between frontmatter 中的 MCP 引用名到实际 MCP 服务器名的映射
- The mapping table SHALL include：capiq→S&P Global, daloopa→Daloopa, factset→FactSet 等

#### Scenario: 映射 Pitch Agent 的 MCP 引用
Given pitch-agent.md frontmatter 中 tools 包含 "mcp__capiq__*"
When 导入脚本处理映射
Then agent_mcps 表正确关联 Pitch Agent 到 S&P Global MCP 服务器

### Requirement: 增量导入
- The system SHALL support importing某一类数据（agents / verticals / mcps）
- Other imported data SHALL NOT be affected已导入数据

#### Scenario: 仅导入 MCP 配置
Given agents 和 verticals 已导入
When 调用 POST /api/import/mcps
Then 仅更新 mcp_servers 表和相关关联表，agents 和 verticals 数据不变
