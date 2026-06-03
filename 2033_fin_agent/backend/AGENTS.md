# Backend — FastAPI Service

This is `backend/AGENTS.md`. Read root `../AGENTS.md` first.

## Stack

- **Python**: 3.11+
- **Framework**: FastAPI + uvicorn
- **Async**: `asyncio` everywhere. NO sync I/O in request handlers.
- **DB client**: `supabase-py` (async)
- **MCP adapter**: `mcp-use` (specifically `OpenAIMCPAdapter`)
- **LLM client**: `openai` SDK with custom `base_url` (works for GLM-5, OpenAI, any OpenAI-compatible endpoint)
- **Validation**: Pydantic v2
- **Testing**: pytest + pytest-asyncio + httpx
- **Lint**: ruff + pyright (strict)
- **Package manager**: `uv` (fast, deterministic)

## Directory Structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── api/                     # Routers (one file per resource)
│   │   ├── agents.py            # GET /agents, GET /agents/{slug}
│   │   ├── chat.py              # Sessions & messages (SSE streaming)
│   │   ├── verticals.py
│   │   ├── mcp.py               # MCP server management
│   │   └── admin.py             # Model config, data import triggers
│   ├── core/
│   │   ├── config.py            # Pydantic Settings (env-driven)
│   │   ├── deps.py              # FastAPI dependencies
│   │   ├── llm.py               # LLM client factory
│   │   └── supabase.py          # Supabase client singleton
│   ├── services/                # Business logic (no FastAPI imports)
│   │   ├── agent_service.py
│   │   ├── chat_service.py      # Orchestrates LLM + MCP tool calls
│   │   └── mcp_service.py
│   ├── adapters/                # External integration
│   │   ├── mcp_adapter.py       # Wraps mcp-use OpenAIMCPAdapter
│   │   └── llm_adapter.py
│   ├── models/                  # Pydantic schemas (request/response)
│   └── importers/               # One-off scripts to import from upstream
│       ├── import_agents.py     # Reads $UPSTREAM_PLUGINS_PATH/agent-plugins/
│       ├── import_skills.py     # Reads vertical-plugins/<vertical>/skills/
│       ├── import_mcps.py       # Reads vertical-plugins/*/.mcp.json
│       └── README.md            # How to run importers
├── tests/
├── pyproject.toml
├── Dockerfile
├── fly.toml                     # Fly.io deployment config
└── .env.example
```

> **Database schema lives OUTSIDE this directory** at `2033_fin_agent/supabase/migrations/`. The migration files are the source of truth for the schema. Backend code reads via the Supabase client; it never duplicates the schema as Python dataclasses.

## Layered Architecture (STRICT)

```
api/ → services/ → adapters/ → external systems
```

- **api/**: Thin FastAPI handlers. Validate input, call service, return response. NO business logic.
- **services/**: Pure business logic. NO FastAPI imports (`Request`, `Depends`, etc.). Returns plain dicts / Pydantic models. Testable without HTTP.
- **adapters/**: Wraps external systems (MCP, LLM, Supabase). Hides library specifics.
- **importers/**: Standalone scripts run via `python -m app.importers.import_agents`. Idempotent.

**Violations**:
- Importing `fastapi.Request` in `services/` → REJECTED
- Calling `openai` directly in `services/` (bypass adapters) → REJECTED
- Business logic in `api/` handler → REJECTED

## Configuration

All config via env vars, loaded by `app/core/config.py` (Pydantic Settings).

```python
# Required env vars
SUPABASE_URL: str
SUPABASE_SERVICE_KEY: str
LLM_BASE_URL: str          # e.g., https://open.bigmodel.cn/api/paas/v4
LLM_API_KEY: str
LLM_MODEL: str             # e.g., glm-5
UPSTREAM_PLUGINS_PATH: str # Absolute path to the upstream plugins/ directory (set per environment)
INTERNAL_ADMIN_TOKEN: str  # Protects write/sensitive endpoints in Phase 1

# Optional
LOG_LEVEL: str = "INFO"
CORS_ORIGINS: str = "http://localhost:3000"
```

NEVER hardcode any of these. NEVER commit `.env`.

## API Conventions

- **REST + SSE for streaming**: Plain JSON for CRUD, Server-Sent Events for chat streaming
- **Paths**: All under `/api/`. Plural nouns. `/api/agents`, `/api/agents/{slug}`, `/api/sessions`, `/api/mcp-servers`
- **Errors**: Standard FastAPI `HTTPException`. Response body uses RFC 7807 problem details shape: `{ "type": "about:blank", "title": "...", "status": 404, "code": "agent_not_found", "detail": "..." }`. Frontend reads `code` for branching and `detail` for display.
- **Pagination**: `?limit=20&offset=0`, response includes `total`
- **Auth (Phase 1)**:
  - Read endpoints: public, no auth
  - Write endpoints (`POST/PUT/DELETE` on `/api/import/*`, `/api/mcp-servers`, `/api/model-configs`): require `X-Admin-Token: <INTERNAL_ADMIN_TOKEN>` header. Validated via FastAPI dependency `require_admin_token`. Mismatch → 401.
  - Chat endpoints: public, sessions are anonymous (no user_id)
  - Phase 2 will replace with Supabase Auth JWT in `Authorization: Bearer <token>`

### Endpoint Catalog (Phase 1)

```
# Public read endpoints
GET    /api/agents
GET    /api/agents/{slug}
GET    /api/verticals
GET    /api/verticals/{slug}
GET    /api/mcp-servers
GET    /api/mcp-servers/{id}
GET    /api/model-configs

# Public chat endpoints (anonymous sessions)
POST   /api/sessions                        # Create session bound to one agent
POST   /api/sessions/{id}/messages          # Send user message, stream agent response via SSE
GET    /api/sessions                        # List sessions (Phase 1: returns all, anonymous)
GET    /api/sessions/{id}                   # Get session detail with full message history
DELETE /api/sessions/{id}                   # Delete a session

# Admin-protected write endpoints (require X-Admin-Token)
POST   /api/import/all                      # Full re-import from $UPSTREAM_PLUGINS_PATH
POST   /api/import/agents
POST   /api/import/verticals
POST   /api/import/mcps
POST   /api/mcp-servers                     # Create MCP server config
PUT    /api/mcp-servers/{id}
POST   /api/model-configs                   # Create model config
PUT    /api/model-configs/{id}
POST   /api/mcp-servers/{id}/test           # Test connection
POST   /api/model-configs/{id}/test         # Test LLM connection

# Health
GET    /health
```

### Streaming Chat Endpoint

`POST /api/sessions/{id}/messages` accepts `{"content": "user message text"}` and returns `Content-Type: text/event-stream`.

The user message is persisted FIRST (returns 200 with SSE headers), then the agent response streams. SSE event names follow the Vercel AI SDK data-stream conventions adapted for our tool-call model:

```
event: message_start
data: {"message_id": "msg_...", "session_id": "ses_..."}

event: token
data: {"delta": "..."}                # Incremental assistant text

event: tool_call
data: {"tool_call_id": "...", "tool": "capiq_get_financials", "args": {...}}

event: tool_result
data: {"tool_call_id": "...", "result": "...", "is_error": false}

event: message_complete
data: {"message_id": "msg_...", "finish_reason": "stop"}

event: error
data: {"code": "llm_timeout", "message": "...", "recoverable": false}

event: done
data: {}                              # Always sent last, even on error, so client can close
```

Rules:
- Every event has a JSON data payload (even empty `{}` for `done`)
- The connection closes after `done`
- Mid-stream errors emit `event: error` then `event: done`, NOT an HTTP error code (the response is already 200)
- `tool_call` may emit MULTIPLE times before its matching `tool_result` (parallel tool calls)
- Frontend matches `tool_call` ↔ `tool_result` by `tool_call_id`

## MCP Integration

- ALL MCP calls go through `app/adapters/mcp_adapter.py`
- The adapter uses `mcp-use` `OpenAIMCPAdapter` to convert MCP tools → OpenAI function definitions
- Tool name mapping (e.g., user-facing `capiq` → upstream `s_and_p_global_capiq`) lives in `mcp_servers` table, populated by importer
- MCP servers are spawned lazily per-chat-session (NOT global singletons — different agents have different MCP access)

## Secret Storage Policy (Phase 1)

- `model_configs.api_key` and `mcp_servers.api_key` are stored as plain `TEXT` columns (nullable for MCPs that don't require keys).
- DO NOT name these columns `api_key_encrypted` — encryption is not implemented in Phase 1, and a misleading name creates a false sense of security.
- API responses MUST NEVER return the plaintext `api_key`. Serializers return either:
  - `has_api_key: bool` — minimal disclosure for list endpoints, or
  - `masked_api_key: str` — last 4 characters prefixed with `****` for detail endpoints (e.g., `"****abc1"`).
- The full plaintext key is only used server-side when calling the LLM / MCP server, never sent to the client.
- Phase 2 will migrate to Supabase Vault or pgcrypto-based encryption at rest, and the column will be renamed at that time.

## Testing

- `tests/unit/`: Pure logic, no I/O. Test services with mocked adapters.
- `tests/integration/`: Real Supabase (test instance), mocked LLM/MCP.
- `tests/e2e/`: Full chat flow with mocked LLM responses.
- Run: `uv run pytest`
- Coverage target: 70% for services, 100% for `adapters/` translation logic.

## Dev Loop

```bash
# Install
uv sync

# Run dev server (hot reload)
uv run uvicorn app.main:app --reload --port 8000

# Lint + type check
uv run ruff check .
uv run pyright

# Run tests
uv run pytest

# Import upstream content into Supabase (one-time per change)
uv run python -m app.importers.import_agents
uv run python -m app.importers.import_skills
uv run python -m app.importers.import_mcps
```

## Deployment (Fly.io)

- `fly.toml` is committed. Single region: `nrt` (Tokyo).
- Secrets via `fly secrets set SUPABASE_URL=...`
- Deploy: `fly deploy`
- Health check: `GET /health` returns 200
- Add region later: `fly regions add iad`

## Anti-Patterns (BLOCKING)

- Sync I/O in handlers (`requests.get`, `time.sleep`, blocking DB call)
- Storing MCP server state in module-level globals
- Hardcoding agent slugs / skill paths in business logic (read from DB)
- Catching `Exception` broadly without re-raising or logging
- Using `print()` for logging (use `logging` module)
- Putting LLM API keys in code, even as "examples"

## What Belongs Here vs Frontend

- **Backend**: Anything touching DB, LLM, MCP. All business logic.
- **Frontend**: Pure UI state, optimistic updates, form validation, display formatting.
- **Shared types**: Generate OpenAPI schema from FastAPI → `openapi.json` → frontend uses `openapi-typescript` to generate TS types. NEVER hand-duplicate types.
