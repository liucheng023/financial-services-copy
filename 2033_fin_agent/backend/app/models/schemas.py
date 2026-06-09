from __future__ import annotations

from pydantic import BaseModel, Field


class SkillSummary(BaseModel):
    slug: str
    name: str
    description: str | None = None


class McpServerSummary(BaseModel):
    id: str
    slug: str
    name: str
    url: str
    transport: str
    has_api_key: bool = False


class AgentListItem(BaseModel):
    slug: str
    name: str
    description: str | None = None
    skill_count: int = 0
    mcp_count: int = 0


class AgentDetail(AgentListItem):
    system_prompt: str
    workflow: str | None = None
    guardrails: str | None = None
    outputs: str | None = None
    skills: list[SkillSummary] = Field(default_factory=list)
    mcps: list[McpServerSummary] = Field(default_factory=list)


class VerticalListItem(BaseModel):
    slug: str
    name: str
    description: str | None = None
    skill_count: int = 0
    mcp_count: int = 0


class VerticalDetail(VerticalListItem):
    skills: list[SkillSummary] = Field(default_factory=list)
    mcps: list[McpServerSummary] = Field(default_factory=list)


class McpServerListItem(BaseModel):
    id: str
    slug: str
    name: str
    url: str
    transport: str
    description: str | None = None
    has_api_key: bool = False


class McpServerDetail(McpServerListItem):
    tool_name_map: dict[str, str] = Field(default_factory=dict)
    masked_api_key: str | None = None


class McpServerCreateRequest(BaseModel):
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    transport: str = "http"
    description: str | None = None
    api_key: str | None = None
    tool_name_map: dict[str, str] = Field(default_factory=dict)


class McpServerUpdateRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    transport: str | None = None
    description: str | None = None
    api_key: str | None = None
    tool_name_map: dict[str, str] | None = None


# ---------------------------------------------------------------------------
# Model configs (Task 8)
#
# Secret policy mirrors mcp_servers: the raw ``api_key`` column is plain TEXT
# in Phase 1 (see supabase/migrations/0001_initial_schema.sql) but MUST NEVER
# leave the backend in plaintext. List endpoints expose ``has_api_key``;
# detail endpoints additionally expose ``masked_api_key`` (``****<last4>``).
# ---------------------------------------------------------------------------


class ModelConfigListItem(BaseModel):
    id: str
    slug: str
    name: str
    base_url: str
    model_name: str
    is_default: bool = False
    has_api_key: bool = False


class ModelConfigDetail(ModelConfigListItem):
    temperature: float = 0.70
    max_tokens: int | None = None
    masked_api_key: str | None = None


class ModelConfigCreateRequest(BaseModel):
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    temperature: float = 0.70
    max_tokens: int | None = None
    is_default: bool = False


class ModelConfigUpdateRequest(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    is_default: bool | None = None


class ModelConfigTestResult(BaseModel):
    # ``ok`` is the only field the frontend should branch on. ``error_code``
    # is a stable short string (e.g. ``connection_error``); ``error_message``
    # is a human-readable summary with provider/url/api_key scrubbed by the
    # adapter (see llm_adapter._sanitize_error).
    ok: bool
    latency_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Chat sessions / messages (Task 7)
#
# Phase 1 sessions are anonymous (chat_sessions.user_id is NULL). Phase 2 will
# tie sessions to authenticated users via Supabase Auth and backfill user_id.
# ---------------------------------------------------------------------------


class SessionCreateRequest(BaseModel):
    agent_slug: str = Field(min_length=1)
    title: str | None = None
    model_config_id: str | None = None


class SessionListItem(BaseModel):
    id: str
    agent_slug: str
    agent_name: str
    title: str | None = None
    created_at: str
    updated_at: str


class ChatMessage(BaseModel):
    id: str
    role: str
    content: str | None = None
    finish_reason: str | None = None
    created_at: str


class SessionDetail(SessionListItem):
    model_config_id: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)
