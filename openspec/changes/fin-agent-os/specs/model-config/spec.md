# model-config Spec

## ADDED Requirements

### Requirement: 模型配置列表
- The page SHALL display all已配置的模型
- Each configuration SHALL display：名称、base_url、model_name、API key 脱敏显示

#### Scenario: 浏览模型配置
Given 用户已配置 GLM-5 模型
When 用户访问系统配置页
Then 显示 GLM-5 配置卡片，API key 显示为"****xxxx"

### Requirement: 新增/编辑模型配置
- Form fields SHALL include：名称、Base URL、API Key、Model Name、Temperature、Max Tokens
- 支持测试连接

#### Scenario: 配置 GLM-5 模型
Given 用户点击新增模型配置
When 用户填写 base_url="https://open.bigmodel.cn/api/paas/v4"，api_key，model_name="glm-5"
Then 系统保存配置，api_key 列以明文 TEXT 存储（Phase 1），后续 API 响应中以脱敏形式返回

#### Scenario: 测试模型连接
Given 用户已配置 GLM-5
When 用户点击"测试连接"
Then 系统发送简单消息验证配置，成功显示"连接正常"，失败显示错误信息

### Requirement: 默认模型
- The system SHALL allow setting one模型配置为默认
- New conversations SHALL automatically use使用默认模型

#### Scenario: 设置默认模型
Given 用户已配置 GLM-5 和 GPT-4o
When 用户将 GLM-5 设为默认
Then 新建对话时自动使用 GLM-5 模型

### Requirement: API Key 不外泄
- API Keys SHALL be stored as plain TEXT in Phase 1（Phase 2 迁移到 Supabase Vault 或 pgcrypto 加密）
- API Keys MUST NOT be returned in any API response in plaintext
- List endpoints SHALL expose `has_api_key: bool`; detail endpoints MAY expose `masked_api_key`（如 `****xxxx`）

#### Scenario: API Key 不外泄
Given 用户提交了 API Key
When 后端保存到 Supabase 并响应客户端
Then 数据库中以明文 TEXT 存储（Phase 1），API 响应不返回明文，仅返回 `has_api_key` 或 `masked_api_key`（如 `****xxxx`）
