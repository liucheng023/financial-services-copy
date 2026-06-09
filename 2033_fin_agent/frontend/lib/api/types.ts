export interface AgentListItem {
  slug: string;
  name: string;
  description: string | null;
  skill_count: number;
  mcp_count: number;
}

export interface AgentDetail extends AgentListItem {
  system_prompt: string;
  workflow: string | null;
  guardrails: string | null;
  outputs: string | null;
  skills: SkillSummary[];
  mcps: McpServerSummary[];
}

export interface SkillSummary {
  slug: string;
  name: string;
  description: string | null;
}

export interface McpServerSummary {
  id: string;
  slug: string;
  name: string;
  url: string;
  transport: string;
  has_api_key: boolean;
}

export interface SessionCreateRequest {
  agent_slug: string;
  title?: string;
  model_config_id?: string;
}

export interface SessionListItem {
  id: string;
  agent_slug: string;
  agent_name: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string | null;
  finish_reason: string | null;
  created_at: string;
}

export interface SessionDetail extends SessionListItem {
  model_config_id: string | null;
  messages: ChatMessage[];
}

export interface SendMessageRequest {
  content: string;
}

export type SseEvent =
  | { type: "message_start"; message_id: string; session_id: string }
  | { type: "token"; delta: string }
  | { type: "message_complete"; message_id: string; finish_reason: string }
  | { type: "error"; code: string; message: string; recoverable: boolean }
  | { type: "done" };
