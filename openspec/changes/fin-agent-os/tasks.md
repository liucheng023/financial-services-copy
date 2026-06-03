# FinAgentOS Phase 1 — Tasks

## Batch 0: Plan Hygiene (DONE)

Completed before any code. Fixes:
- Frontend stack unified to Next.js 14 App Router + TypeScript + Tailwind + shadcn/ui + TanStack Query + Zustand + pnpm (removed all React/Vite/React Router references)
- Auth scope unified: Phase 1 = no user auth, admin token on write endpoints, Phase 2 = Supabase Auth
- Upstream path: all references use `UPSTREAM_PLUGINS_PATH` env var, no hardcoded paths
- API contract unified: session-based `/api/sessions` + `/api/sessions/{id}/messages` with SSE, Vercel AI SDK-style event protocol
- Tasks restructured into fine-grained deliverables with verification criteria

---

## Batch 1: Foundation (Backend First)

### Task 1: Supabase Schema Contract

- [ ] Write SQL migration `2033_fin_agent/supabase/migrations/0001_initial_schema.sql` covering all tables: `agents`, `skills`, `verticals`, `mcp_servers`, `agent_skills`, `agent_mcps`, `vertical_skills`, `vertical_mcps`, `chat_sessions`, `chat_messages`, `model_configs`
- [ ] `chat_sessions.user_id` MUST be `UUID NULL` (Phase 2 migration readiness)
- [ ] `model_configs.api_key` and `mcp_servers.api_key` stored as plain `TEXT` (NOT `_encrypted` — see backend/AGENTS.md "Secret Storage Policy"). `mcp_servers.api_key` is nullable.
- [ ] Include unique constraints on `slug` columns and on association-table composite keys
- [ ] Include indexes: `agents(slug)`, `skills(slug)`, `verticals(slug)`, `mcp_servers(slug)`, `chat_sessions(agent_id)`, `chat_messages(session_id, created_at)`
- [ ] `chat_messages` covers: `role`, `content`, `tool_calls` (jsonb), `tool_results` (jsonb), `created_at`
- [ ] Add SQL comments at the top of `mcp_servers` and `model_configs` documenting the secret-disclosure policy (responses never return plaintext `api_key`)
- [ ] Statically validate the SQL: pipe through `psql --no-psqlrc -f - --set ON_ERROR_STOP=1` against a throwaway local Postgres (e.g., `docker run --rm -d postgres:16`) — this proves the SQL parses and executes, without committing to a real Supabase project.
- [ ] If a real Supabase project + service-role credentials are available, apply the migration there and record the result; otherwise SKIP this step and explicitly note "no Supabase environment available yet".
- **Deliverable**: `2033_fin_agent/supabase/migrations/0001_initial_schema.sql` committed; SQL passes syntactic + structural validation on a throwaway Postgres
- **Verification**: Container run logs show all `CREATE TABLE` / `CREATE INDEX` succeed with exit code 0; `\dt` lists all 11 tables; `\d+ chat_sessions` shows `user_id` as nullable UUID

### Task 2: Importer — Agent Parser

- [ ] Write `backend/app/importers/import_agents.py`:
  - Read `$UPSTREAM_PLUGINS_PATH/agent-plugins/*/agents/*.md`
  - Parse frontmatter (name, slug, tools list, etc.) and body (system prompt)
  - Parse `plugin.json` for metadata
  - Write to `agents` + `agent_skills` + `agent_mcps` tables in Supabase
- [ ] Must be idempotent (re-run overwrites existing rows)
- [ ] Must be read-only relative to upstream filesystem
- **Deliverable**: Script runs, Supabase `agents` table has 10 rows
- **Verification**: `SELECT count(*) FROM agents` = 10; spot-check `pitch-agent` system_prompt is non-empty

### Task 3: Importer — Skill + Vertical + MCP Parsers

- [ ] Write `backend/app/importers/import_skills.py`:
  - Read `$UPSTREAM_PLUGINS_PATH/vertical-plugins/*/skills/*/SKILL.md`
  - Parse frontmatter + content
  - Write to `skills` + `vertical_skills` tables
- [ ] Write `backend/app/importers/import_verticals.py`:
  - Read `$UPSTREAM_PLUGINS_PATH/vertical-plugins/*/plugin.json`
  - Write to `verticals` table
- [ ] Write `backend/app/importers/import_mcps.py`:
  - Read `$UPSTREAM_PLUGINS_PATH/financial-analysis/.mcp.json` (all MCPs centralized here)
  - Build MCP tool name mapping table (capiq → S&P Global Kensho, etc.)
  - Write to `mcp_servers` + `vertical_mcps` + `agent_mcps` tables
- [ ] Write `backend/app/importers/import_all.py`: calls all four in sequence
- [ ] All scripts idempotent and read-only relative to upstream
- **Deliverable**: All importers run; Supabase has 7 verticals, 50+ skills, 11 MCPs
- **Verification**: `SELECT count(*) FROM skills` ≥ 50; `SELECT count(*) FROM mcp_servers` = 11; `SELECT slug, url FROM mcp_servers LIMIT 3` returns real URLs

### Task 4: Backend Scaffold

- [ ] Initialize FastAPI project: `pyproject.toml`, `uv` config, Python 3.11+
- [ ] `app/main.py`: FastAPI app with CORS, `/health` endpoint
- [ ] `app/core/config.py`: Pydantic Settings loading all env vars (SUPABASE_URL, SUPABASE_SERVICE_KEY, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, UPSTREAM_PLUGINS_PATH, INTERNAL_ADMIN_TOKEN, CORS_ORIGINS, LOG_LEVEL)
- [ ] `app/core/supabase.py`: async Supabase client singleton
- [ ] `app/core/deps.py`: `require_admin_token` dependency
- [ ] `app/api/agents.py`: `GET /api/agents`, `GET /api/agents/{slug}` (read from Supabase)
- [ ] `Dockerfile` + `fly.toml` (region nrt)
- [ ] `.env.example`
- **Deliverable**: `uv run uvicorn app.main:app` starts; `GET /health` returns 200; `GET /api/agents` returns JSON (after importers run)
- **Verification**: curl test against running dev server

## Batch 2: Backend Core

### Task 5: Read-only APIs (Agents, Verticals, MCPs)

- [ ] `GET /api/agents` (list with skill_count, mcp_count)
- [ ] `GET /api/agents/{slug}` (detail with skills list, mcps list, workflow, guardrails)
- [ ] `GET /api/verticals` (list)
- [ ] `GET /api/verticals/{slug}` (detail with skills, mcps)
- [ ] `GET /api/mcp-servers` (list with status indicator)
- [ ] `GET /api/mcp-servers/{id}` (detail with tool list)
- [ ] `POST /api/mcp-servers` (admin-protected, create new MCP config)
- [ ] `PUT /api/mcp-servers/{id}` (admin-protected)
- [ ] Add `X-Admin-Token` validation on write endpoints
- **Deliverable**: All CRUD endpoints return correct data from Supabase
- **Verification**: curl/pytest against each endpoint; admin token required on POST/PUT

### Task 6: MCP Adapter Layer

- [ ] Integrate `mcp-use` library (`pip install mcp-use`)
- [ ] `app/adapters/mcp_adapter.py`:
  - Load MCP server configs from Supabase for a given agent
  - Initialize MCPClient connections
  - Use OpenAIMCPAdapter to convert tools → OpenAI function schema
  - Implement tool_executors: model returns tool_calls → execute via adapter → return results
- [ ] `app/services/mcp_service.py`: business logic wrapping the adapter
- [ ] Lazy initialization per chat session (different agents have different MCP access)
- [ ] Graceful degradation: if an MCP server is unreachable, log warning, skip its tools
- **Deliverable**: Given an agent slug, MCP adapter returns a list of OpenAI function definitions + can execute tool calls
- **Verification**: Unit test: mock MCP server → adapter returns function schema → mock tool_call → returns result

### Task 7: Chat Session + Streaming Engine

- [ ] `POST /api/sessions` — create session bound to an agent, load agent's system prompt + skills + MCP tools into session context
- [ ] `POST /api/sessions/{id}/messages` — accept user message, stream agent response via SSE per Decision 8 protocol
- [ ] Implement function calling loop: model → tool_calls → execute via MCP adapter → feed results back → repeat until model stops
- [ ] Implement context window management (system prompt + history + current; truncate oldest if over limit)
- [ ] `GET /api/sessions` — list sessions
- [ ] `GET /api/sessions/{id}` — session detail + message history
- [ ] `DELETE /api/sessions/{id}` — delete session
- [ ] Persist all messages (user + assistant + tool_calls + tool_results) to `chat_messages`
- **Deliverable**: Full chat loop works: create session → send message → receive streaming response with tool calls
- **Verification**: curl POST creates session; curl POST sends message; SSE stream shows token/tool_call/tool_result/done events; messages persisted in DB

### Task 8: Model Config API

- [ ] `GET /api/model-configs` (list)
- [ ] `POST /api/model-configs` (admin-protected, create config with base_url, api_key, model_name, temperature, max_tokens)
- [ ] `PUT /api/model-configs/{id}` (admin-protected, update)
- [ ] `POST /api/model-configs/{id}/test` — send a trivial message to verify the LLM endpoint works
- [ ] `GET /api/model-configs/default` — return the currently active model config
- **Deliverable**: Can configure GLM-5 endpoint, test connection, and chat uses the configured model
- **Verification**: Create GLM-5 config via API → test returns 200 → create session → send message → response comes from GLM-5

## Batch 3: Frontend (After API Contract Stable)

### Task 9: Next.js Scaffold + Layout

- [ ] Initialize Next.js 14 project: `pnpm create next-app` with App Router + TypeScript + Tailwind
- [ ] Install shadcn/ui, TanStack Query, Zustand, nuqs
- [ ] Generate API types from backend OpenAPI: `pnpm generate-api`
- [ ] Root layout with sidebar (experts, skills, MCPs, history, settings)
- [ ] App Router routes matching design.md page structure
- [ ] Dark mode via next-themes
- **Deliverable**: `pnpm dev` runs; sidebar navigates between placeholder pages; dark mode toggles
- **Verification**: Browser shows sidebar + placeholder content; all routes resolve

### Task 10: Agent Marketplace + Detail Pages

- [ ] `app/agents/page.tsx` — 10 Agent cards (name, description, skill count, MCP count) from `GET /api/agents`
- [ ] `app/agents/[slug]/page.tsx` — Agent detail (role, workflow, skills, MCPs, guardrails) from `GET /api/agents/{slug}`
- [ ] "Start Chat" button → navigate to `/agents/{slug}/chat`
- **Deliverable**: All 10 agents visible; detail page shows full info
- **Verification**: Browse agents list → click one → see full detail → click "Start Chat" → navigates correctly

### Task 11: Chat Page

- [ ] `app/agents/[slug]/chat/page.tsx` — main chat UI
- [ ] Create session on mount: `POST /api/sessions`
- [ ] Chat input → `POST /api/sessions/{id}/messages` → SSE stream via fetch + ReadableStream
- [ ] Message list: UserMessage, AssistantMessage (streaming), ToolCallMessage (collapsible)
- [ ] Agent selector (switch agent → confirm → new session)
- **Deliverable**: Can chat with an agent, see streaming tokens, see tool calls
- **Verification**: Type message → see streaming response → tool calls shown → chat persists after refresh

### Task 12: Vertical + MCP + Config Pages

- [ ] `app/verticals/page.tsx` — 7 vertical cards
- [ ] `app/mcp-servers/page.tsx` — 11 MCP cards with status
- [ ] `app/admin/settings/page.tsx` — model config list + create form + test connection + admin token input
- **Deliverable**: All management pages functional
- **Verification**: Browse verticals → see skills/MCPs; config page → create GLM-5 config → test succeeds

### Task 13: Chat History Page

- [ ] `app/history/page.tsx` — sessions list (sorted by date, filterable by agent)
- [ ] Click session → replay view (full message history, tool calls collapsible)
- [ ] Delete session
- **Deliverable**: History browsable, sessions replayable, deletable
- **Verification**: After chat → go to history → see session → click → replay → delete → gone

## Batch 4: Integration & E2E

### Task 14: End-to-End Smoke Test

- [ ] Import data → configure GLM-5 → select Pitch Agent → send message → receive streaming response
- [ ] MCP tool call works in chat (at least 1 MCP)
- [ ] Agent switch works (new session, fresh context)
- [ ] Chat history saves and replays correctly
- [ ] Admin-protected endpoints reject requests without valid token
- **Deliverable**: Core flow end-to-end working on deployed or local environment
- **Verification**: Walk through the full flow manually or via pytest e2e
