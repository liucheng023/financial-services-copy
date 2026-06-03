-- FinAgentOS Phase 1 — Initial Schema
-- Migration: 0001_initial_schema
-- Location:  2033_fin_agent/supabase/migrations/0001_initial_schema.sql
--
-- This file is the source of truth for the FinAgentOS Phase 1 database schema.
-- Backend code reads via the Supabase client; never duplicate the schema as
-- Python dataclasses.
--
-- SECRET STORAGE POLICY (Phase 1):
--   * mcp_servers.api_key and model_configs.api_key are stored as plain TEXT.
--   * Encryption at rest is NOT implemented in Phase 1. The column name does
--     NOT use the "_encrypted" suffix to avoid a false sense of security.
--   * API responses MUST NEVER return plaintext api_key. Serializers expose
--     either `has_api_key: bool` or `masked_api_key: "****xxxx"`.
--   * Phase 2 will migrate to Supabase Vault / pgcrypto encryption and rename
--     the column at that time.

BEGIN;

-- Required for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Core entity tables
-- ---------------------------------------------------------------------------

CREATE TABLE agents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT,
    system_prompt   TEXT NOT NULL,
    workflow        TEXT,
    guardrails      TEXT,
    outputs         TEXT,
    raw_frontmatter JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_agents_slug ON agents (slug);

CREATE TABLE verticals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT,
    raw_manifest    JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_verticals_slug ON verticals (slug);

CREATE TABLE skills (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT,
    vertical_id     UUID REFERENCES verticals (id) ON DELETE SET NULL,
    content         TEXT NOT NULL,
    raw_frontmatter JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_skills_slug ON skills (slug);
CREATE INDEX idx_skills_vertical_id ON skills (vertical_id);

-- ---------------------------------------------------------------------------
-- MCP servers
--
-- SECRETS NOTE: api_key is plaintext TEXT in Phase 1 and MUST NOT be exposed
-- to clients. See file-level header.
-- ---------------------------------------------------------------------------
CREATE TABLE mcp_servers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    url             TEXT NOT NULL,
    description     TEXT,
    api_key         TEXT,              -- Phase 1: plaintext, nullable; never returned in API responses
    transport       TEXT NOT NULL DEFAULT 'http',
    tool_name_map   JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_manifest    JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_mcp_servers_slug ON mcp_servers (slug);
COMMENT ON COLUMN mcp_servers.api_key IS
  'Phase 1: plaintext TEXT, nullable. API responses MUST expose only has_api_key/masked_api_key. Phase 2 will encrypt.';

-- ---------------------------------------------------------------------------
-- Association tables (composite primary keys)
-- ---------------------------------------------------------------------------

CREATE TABLE agent_skills (
    agent_id    UUID NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
    skill_id    UUID NOT NULL REFERENCES skills (id) ON DELETE CASCADE,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (agent_id, skill_id)
);
CREATE INDEX idx_agent_skills_skill_id ON agent_skills (skill_id);

CREATE TABLE agent_mcps (
    agent_id        UUID NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
    mcp_server_id   UUID NOT NULL REFERENCES mcp_servers (id) ON DELETE CASCADE,
    PRIMARY KEY (agent_id, mcp_server_id)
);
CREATE INDEX idx_agent_mcps_mcp_server_id ON agent_mcps (mcp_server_id);

CREATE TABLE vertical_skills (
    vertical_id     UUID NOT NULL REFERENCES verticals (id) ON DELETE CASCADE,
    skill_id        UUID NOT NULL REFERENCES skills (id) ON DELETE CASCADE,
    PRIMARY KEY (vertical_id, skill_id)
);
CREATE INDEX idx_vertical_skills_skill_id ON vertical_skills (skill_id);

CREATE TABLE vertical_mcps (
    vertical_id     UUID NOT NULL REFERENCES verticals (id) ON DELETE CASCADE,
    mcp_server_id   UUID NOT NULL REFERENCES mcp_servers (id) ON DELETE CASCADE,
    PRIMARY KEY (vertical_id, mcp_server_id)
);
CREATE INDEX idx_vertical_mcps_mcp_server_id ON vertical_mcps (mcp_server_id);

-- ---------------------------------------------------------------------------
-- Model configs
--
-- SECRETS NOTE: api_key is plaintext TEXT in Phase 1 and MUST NOT be exposed
-- to clients. See file-level header.
-- ---------------------------------------------------------------------------
CREATE TABLE model_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    base_url        TEXT NOT NULL,
    api_key         TEXT NOT NULL,     -- Phase 1: plaintext; never returned in API responses
    model_name      TEXT NOT NULL,
    temperature     NUMERIC(4,2) NOT NULL DEFAULT 0.70,
    max_tokens      INTEGER,
    is_default      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_model_configs_slug ON model_configs (slug);
CREATE UNIQUE INDEX idx_model_configs_one_default
    ON model_configs ((1)) WHERE is_default = TRUE;
COMMENT ON COLUMN model_configs.api_key IS
  'Phase 1: plaintext TEXT. API responses MUST expose only has_api_key/masked_api_key. Phase 2 will encrypt.';

-- ---------------------------------------------------------------------------
-- Chat sessions and messages
--
-- user_id is intentionally nullable to keep Phase 2 (Supabase Auth) migration
-- friction-free: Phase 1 sessions are anonymous; Phase 2 will backfill the
-- column from authenticated requests.
-- ---------------------------------------------------------------------------
CREATE TABLE chat_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NULL,         -- Phase 2 will populate from auth.users
    agent_id            UUID NOT NULL REFERENCES agents (id) ON DELETE RESTRICT,
    model_config_id     UUID REFERENCES model_configs (id) ON DELETE SET NULL,
    title               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_sessions_agent_id ON chat_sessions (agent_id);
CREATE INDEX idx_chat_sessions_user_id ON chat_sessions (user_id);
CREATE INDEX idx_chat_sessions_created_at ON chat_sessions (created_at DESC);

CREATE TABLE chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES chat_sessions (id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content         TEXT,
    tool_calls      JSONB,
    tool_results    JSONB,
    finish_reason   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_messages_session_id_created_at
    ON chat_messages (session_id, created_at);

COMMIT;
