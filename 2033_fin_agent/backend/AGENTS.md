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
│   │   ├── chat.py              # POST /chat (SSE streaming)
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
│       ├── import_agents.py     # Reads /root/financial_agent/plugins/agent-plugins/
│       ├── import_skills.py     # Reads vertical-plugins/<vertical>/skills/
│       ├── import_mcps.py       # Reads vertical-plugins/*/.mcp.json
│       └── README.md            # How to run importers
├── tests/
├── pyproject.toml
├── Dockerfile
├── fly.toml                     # Fly.io deployment config
└── .env.example
```

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
UPSTREAM_PLUGINS_PATH: str # e.g., /root/financial_agent/plugins (for importers)

# Optional
LOG_LEVEL: str = "INFO"
CORS_ORIGINS: str = "http://localhost:3000"
```

NEVER hardcode any of these. NEVER commit `.env`.

## API Conventions

- **REST + SSE for streaming**: Plain JSON for CRUD, Server-Sent Events for chat streaming
- **Paths**: Plural nouns. `/agents`, `/agents/{slug}`, `/chat`, `/mcp-servers`
- **Errors**: Standard FastAPI `HTTPException` with structured detail. Frontend reads `error.detail.code` + `error.detail.message`.
- **Pagination**: `?limit=20&offset=0`, response includes `total`
- **Auth**: Phase 1 = Supabase Auth JWT in `Authorization: Bearer <token>`. Validated via dependency.

### Streaming Chat Endpoint

`POST /chat` returns `text/event-stream`. Events:

```
event: token
data: {"content": "..."}

event: tool_call
data: {"tool": "capiq_get_financials", "args": {...}}

event: tool_result
data: {"tool": "capiq_get_financials", "result": "..."}

event: done
data: {"message_id": "..."}

event: error
data: {"code": "...", "message": "..."}
```

## MCP Integration

- ALL MCP calls go through `app/adapters/mcp_adapter.py`
- The adapter uses `mcp-use` `OpenAIMCPAdapter` to convert MCP tools → OpenAI function definitions
- Tool name mapping (e.g., user-facing `capiq` → upstream `s_and_p_global_capiq`) lives in `mcp_servers` table, populated by importer
- MCP servers are spawned lazily per-chat-session (NOT global singletons — different agents have different MCP access)

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
