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
