# chat-history Spec

## ADDED Requirements

### Requirement: 聊天记录列表
- Sessions SHALL be displayed in reverse chronological order所有对话会话
- Each record SHALL display：关联的 Agent 名称、首条消息摘要、创建时间
- Filtering by Agent SHALL be supported 筛选

#### Scenario: 浏览聊天记录
Given 用户有 5 条历史对话
When 用户访问聊天记录页
Then 显示 5 条记录按时间倒序，每条显示 Agent 名称和首条消息摘要

### Requirement: 聊天记录详情
- The detail view SHALL display the complete message history (user messages + assistant messages + tool calls)
- Tool calls SHALL be collapsible and expandable
- The view SHALL be read-only

#### Scenario: 查看历史对话
Given 用户点击一条与 Pitch Agent 的历史对话
Then 展示完整消息历史，工具调用可折叠查看参数和结果，不可编辑

### Requirement: 聊天记录删除
- The system SHALL support single and batch deletion和批量删除
- Deletion SHALL require confirmation

#### Scenario: 删除聊天记录
Given 用户选中 2 条历史对话
When 用户点击删除
Then 弹出确认对话框，确认后删除这 2 条记录
