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
Then 系统保存配置，API key 加密存储

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

### Requirement: 配置加密存储
- API Keys SHALL be stored using Supabase 加密功能存储
- API Keys SHALL NOT be returned API 响应中返回明文

#### Scenario: API Key 安全存储
Given 用户提交了 API Key
When 后端保存到 Supabase
Then API Key 加密存储，GET API 返回时脱敏为"****xxxx"
