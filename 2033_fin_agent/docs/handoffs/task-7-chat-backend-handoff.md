# Task 7 — Chat Session CRUD + SSE Streaming Engine (Backend Handoff)

**Commits**: `e4b9e19` (feat), `436d683` (fix: service boundary), `02803b6` (fix: SSE identity)
**Date**: 2026-06-09
**Status**: Done — passed parameter (参谋) review

---

## 1. Chat API Surface

All endpoints under `/api` prefix, mounted via `chat_router` in `app/main.py`.

| Method | Path | Status | Content-Type | Auth |
|---|---|---|---|---|
| `POST` | `/api/sessions` | 201 | `application/json` | Public (Phase 1) |
| `GET` | `/api/sessions` | 200 | `application/json` | Public (Phase 1) |
| `GET` | `/api/sessions/{id}` | 200 / 404 | `application/json` | Public (Phase 1) |
| `POST` | `/api/sessions/{id}/messages` | 200 / 404 | `text/event-stream` | Public (Phase 1) |

**`DELETE /api/sessions/{id}` does NOT exist.** Removed in `436d683` — Phase 1 sessions are anonymous, so a public destructive endpoint would let any caller wipe any session. Re-introduce only behind `require_admin_token` (or Phase 2 Supabase Auth + RLS) with explicit ownership checks.

All 4xx error responses follow RFC 7807 problem-details JSON shape:

```json
{
  "type": "about:blank",
  "title": "Session not found",
  "status": 404,
  "code": "session_not_found",
  "detail": "No chat session with id '...'."
}
```

Error codes:

| Code | HTTP | Meaning |
|---|---|---|
| `agent_not_found` | 404 | `SessionCreateRequest.agent_slug` does not match any agent |
| `session_not_found` | 404 | Session id not found (GET detail or POST message) |
| `model_config_not_found` | 404 | No model config is marked as default (and no explicit override resolved) |

---

## 2. Request / Response Schema Summary

All models in `app/models/schemas.py`.

### POST /api/sessions — Request body

```
SessionCreateRequest:
  agent_slug: str            # required, min_length=1 — FK to agents.slug
  title: str | None          # optional display title
  model_config_id: str | None  # optional — overrides the default model for this session
```

### POST /api/sessions — Response (201)

```
SessionDetail:
  id: str
  agent_slug: str
  agent_name: str
  title: str | None
  model_config_id: str | None
  created_at: str            # ISO 8601
  updated_at: str            # ISO 8601
  messages: list[ChatMessage]  # always [] on creation
```

### GET /api/sessions — Response (200)

```
SessionListItem:
  id: str
  agent_slug: str
  agent_name: str
  title: str | None
  created_at: str
  updated_at: str
```

Pagination not yet implemented — returns all sessions.

### GET /api/sessions/{id} — Response (200)

Same `SessionDetail` shape, with `messages` populated from `chat_messages` ordered by `created_at`.

### POST /api/sessions/{id}/messages — Request body

```
SendMessageRequest:
  content: str               # required, min_length=1 — user message text
```

Response is an SSE stream (see Section 3).

---

## 3. SSE Event Protocol

Response headers:

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

### Success sequence

```
event: message_start
data: {"message_id": "<assistant_msg_id>", "session_id": "<session_id>"}

event: token
data: {"delta": "..."}               # one per LLM streaming chunk

event: message_complete
data: {"message_id": "<same_assistant_msg_id>", "finish_reason": "stop"}

event: done
data: {}
```

### Mid-stream error sequence (HTTP stays 200)

```
event: message_start
data: {"message_id": "<assistant_msg_id>", "session_id": "<session_id>"}

event: error
data: {"code": "timeout|stream_failed|...", "message": "...", "recoverable": false}

event: done
data: {}
```

### Rules

- Every event has a JSON `data` payload. `done` carries `{}`.
- The connection closes after `done`.
- Mid-stream errors emit `event: error` then `event: done` — NOT an HTTP error code (the response is already 200).
- `tool_call` / `tool_result` events are **defined** in `backend/AGENTS.md` but **not emitted yet** (reserved for MCP integration).

---

## 4. `message_id` Semantics (commit `02803b6`)

`message_start.message_id` and `message_complete.message_id` are the **same ID**, pointing to the **assistant message row** in `chat_messages`.

Flow:

1. User message INSERTed to `chat_messages` (role=`user`, content=`<user text>`).
2. Assistant **placeholder row** INSERTed before streaming begins (role=`assistant`, content=`""`, finish_reason=`NULL`).
3. `message_start` broadcasts the placeholder's `id`.
4. Placeholder is **excluded from LLM context** by filtering on `id` in `_load_history`.
5. **On success**: placeholder row is UPDATEd with `content=<accumulated text>` + `finish_reason="stop"`. `message_complete` uses the same `id`.
6. **On error**: placeholder row is UPDATEd with `finish_reason="error"`, `content=""` stays empty. SSE emits `error -> done`.

This guarantees:
- A single stable `message_id` across the entire SSE lifecycle.
- A persisted assistant row always exists (even on error) matching the `id` already broadcast in `message_start`.
- A subsequent `GET /api/sessions/{id}` returns a consistent record with both user and assistant messages.

The persisted `chat_messages` table always contains exactly 2 rows per successful turn: 1 user, 1 assistant.

---

## 5. LLM Config Boundary

The runtime LLM endpoint is resolved through the **service boundary only**.

### Model resolution

```
# In chat_service.prepare_stream():
from ..services.model_config_service import get_runtime_model_config

model_row = await get_runtime_model_config(client, session_row.get("model_config_id"))
```

- If `session_row["model_config_id"]` is set: fetches that specific config.
- If `model_config_id` is `NULL`: fetches the config with `is_default=True`.
- If neither resolves: raises `NoDefaultModelError` -> router returns `404` with code `model_config_not_found`.

### RuntimeModelConfig (server-only)

```
@dataclass(frozen=True)
class RuntimeModelConfig:
    id: str
    base_url: str
    api_key: str          # raw plaintext — NEVER serialize to API response
    model_name: str
    temperature: float = 0.70
    max_tokens: int | None = None
```

Defined in `app/services/model_config_service.py`. This is the **only** type that carries the raw `api_key`. It is used exclusively inside the request lifecycle to construct an `LLMStreamConfig` for the adapter.

### Hard boundaries

- chat_service does **not** directly call `client.table("model_configs")` (removed in `436d683`).
- Runtime code does **not** read `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` env vars (legacy only).
- All LLM calls go through `app/adapters/llm_adapter.py` -> `http_stream_chat_completion()` async generator.

---

## 6. Test & Verification State

| Check | Result |
|---|---|
| `pytest` | **85 passed, 16 skipped** (importer env-gated — `UPSTREAM_PLUGINS_PATH` not set) |
| `ruff check app/ tests/` | **Clean** — 0 errors |
| `openspec validate fin-agent-os --strict` | **Passes** |
| `pyright` | Skipped — prebuilt node download times out in sandbox (pre-existing, not a regression) |

### Test coverage — `tests/runtime/test_chat_api.py` (9 tests)

| Test | What it covers |
|---|---|
| `test_create_session_success` | 201 + response shape |
| `test_create_session_agent_not_found` | 404 + code=`agent_not_found` |
| `test_list_sessions` | Returns existing session |
| `test_get_session_detail` | Full detail with messages |
| `test_get_session_not_found` | 404 + code=`session_not_found` |
| `test_send_message_streams_tokens_and_persists` | SSE event order, start id == complete id, persisted assistant matches, secret not leaked, placeholder excluded from LLM context |
| `test_send_message_session_not_found` | 404 on missing session |
| `test_send_message_no_default_model` | 404 when no model is default |
| `test_send_message_llm_error_emits_sse_error` | SSE error sequence, `finish_reason="error"` on placeholder row, `message_id` in start event, secret not leaked |

### Test infra

- `FakeAsyncClient` — state-backed fake Supabase client with `_Query` supporting `.select/.eq/.in_/.maybe_single/.order/.insert/.update/.delete/.execute`.
- LLM calls stubbed via `monkeypatch.setattr(svc, "http_stream_chat_completion", fake_stream)`.
- **No real LLM endpoint is called in any automated test.**

---

## 7. Real LLM Status

| Check | Status |
|---|---|
| Gate 7A — `POST /api/model-configs` + `POST /api/model-configs/{id}/test` | Verified against real GLM-5.1 endpoint (`open.bigmodel.cn`). Default model_config seeded with id=`8ce43ebf-...`, slug=`zhipu-coding-glm-51`, model_name=`GLM-5.1`. |
| Gate 7A — chat SSE (`POST /api/sessions/{id}/messages`) | **NOT tested with a real LLM.** Gate 7A ran before `chat_service` existed; it only validated model config creation and connection testing. |
| Task 7 automated tests | **Use fake streamer only.** No test calls a real LLM endpoint. |
| Manual `curl` SSE smoke against real GLM-5.1 | **Not yet executed.** Optional/manual after Task 7. A human operator with a running dev server and valid `model_configs.api_key` in Supabase should run: `curl -X POST /api/sessions -d '{"agent_slug":"pitch-agent"}'` then `curl -N -X POST /api/sessions/{id}/messages -d '{"content":"Hello"}'` and inspect SSE tokens visually. |

---

## 8. Known Limitations (Phase 1)

| Limitation | Details |
|---|---|
| **Anonymous sessions** | `chat_sessions.user_id` is always `NULL`. Any caller can list/create/read any session. |
| **No Auth / RLS on chat endpoints** | Chat endpoints are public (Phase 1 design choice). Only admin-endpoints (`/api/import/*`, `/api/model-configs`, `/api/mcp-servers`) require `X-Admin-Token`. |
| **No DELETE session** | Removed in `436d683`. Re-introduce behind admin-token or Phase 2 Auth + RLS with ownership checks. |
| **No tool_call / tool_result** | SSE event names are defined in the protocol but never emitted. Reserved for MCP integration (later task). |
| **No frontend** | Backend-only. No Next.js UI consumes these endpoints. |
| **No pagination** | `GET /api/sessions` returns all sessions in one response. |
| **No context window management** | Messages appended unconditionally. No truncation when token limit is exceeded. |
| **User message id not in SSE events** | `message_start` broadcasts the assistant message id. The user message id is not exposed in the SSE stream. Frontend can infer it from `GET /api/sessions/{id}` message ordering if needed. |
| **pyright blocked by sandbox** | Prebuilt node download times out in Docker. Type-checking is deferred; existing code has only pre-import-resolution warnings (not new). |

---

## 9. Key Commits

```
e4b9e19 feat(chat): Task 7 — chat session CRUD + SSE streaming engine
436d683 fix(chat): keep runtime model config behind service boundary
02803b6 fix(chat): keep SSE assistant message identity stable
```

---

## 10. Key Files

| File | Purpose |
|---|---|
| `app/api/chat.py` | Thin SSE router — 4 routes, RFC 7807 error helpers |
| `app/services/chat_service.py` | Business logic — session CRUD + stream orchestration |
| `app/services/model_config_service.py` | `RuntimeModelConfig` dataclass + `get_runtime_model_config()` |
| `app/adapters/llm_adapter.py` | `http_stream_chat_completion` async generator, `LLMStreamConfig`, `StreamEvent`, `ChatStreamer` |
| `app/models/schemas.py` | `SessionCreateRequest`, `SessionListItem`, `SessionDetail`, `ChatMessage`, `SendMessageRequest` |
| `app/main.py` | `chat_router` mount point |
| `tests/runtime/test_chat_api.py` | 9 tests — fake Supabase + fake streamer |
| `supabase/migrations/0001_initial_schema.sql` | `chat_sessions` and `chat_messages` DDL reference |

---

## 11. Frontend Integration Notes

### DELETE /api/sessions/{id} does not exist

Phase 1 sessions are anonymous. A public destructive endpoint would let any caller wipe any session. The route, service function, and tests were removed in `436d683`. If the frontend needs session deletion, it must either:
- Wait for Phase 2 Auth (Supabase Auth + RLS + ownership checks), or
- Route through an internal operator/tool interface that sends `X-Admin-Token` (but that makes it an **internal operator tool**, not a public UI).

### SSE event contract for frontend

- `message_start.message_id` is the **assistant message id** — NOT the user message id.
- Each `token` event appends a `delta` fragment to the assistant message being built.
- `message_complete.message_id` is **the same id** as `message_start.message_id`. The frontend can use this to associate the entire assistant message with a single stable key.
- On mid-stream error: `error` event fires (HTTP stays 200), followed immediately by `done`. The assistant placeholder persists in `chat_messages` with `finish_reason="error"` and empty `content`.
- The frontend should always expect `done` as the final event, even after `error`.
- `tool_call` / `tool_result` events are **defined** in `backend/AGENTS.md` protocol but **will not appear** in Phase 1 SSE streams. Do not build UI logic that depends on them until the MCP integration task is complete.

### Token / secret handling

- `INTERNAL_ADMIN_TOKEN` is a server-side deployment secret. A **public frontend must never see, store, or transmit it**.
- `model_configs.api_key` is stored as plain text in Supabase but **never included in API responses**. The frontend receives `ModelConfigDetail.masked_api_key` only (e.g. `"****abcd"`).
- `RuntimeModelConfig` (with raw `api_key`) exists only inside the backend request lifecycle — never serialized to any HTTP response.
- If an admin/settings page needs to send `X-Admin-Token` (for creating/updating model configs), that page is by definition an **internal operator tool** — it must be scoped, documented, and access-restricted, never linked from the public end-user surface.

### Data model mapping

```
chat_sessions row     SessionDetail / SessionListItem
  .id                 .id
  .agent_id           .agent_slug (resolved via agents table join)
  .title              .title
  .created_at         .created_at
  .updated_at         .updated_at

chat_messages row     ChatMessage
  .id                 .id
  .role               .role
  .content            .content
  .finish_reason      .finish_reason
  .created_at         .created_at
```

### End-to-end flow

```
Frontend               Backend                Supabase
  |                      |                      |
  | POST /api/sessions   |                      |
  | {agent_slug, title}  |                      |
  |--------------------->|                      |
  |                      | INSERT chat_sessions |
  |                      |--------------------->|
  | 201 SessionDetail    |                      |
  |<---------------------|                      |
  |                      |                      |
  | POST /api/sessions/  |                      |
  |   {id}/messages      |                      |
  | {content: "Hello"}   |                      |
  |--------------------->|                      |
  |                      | INSERT chat_message  |
  |                      | (role=user)          |
  |                      |--------------------->|
  |                      | INSERT chat_message  |
  |                      | (role=assistant,     |
  |                      |  content="")         |
  |                      |--------------------->|
  | SSE: message_start   |                      |
  | {message_id,         |                      |
  |  session_id}         |                      |
  |<---------------------|                      |
  | SSE: token x N       |  LLM stream          |
  |<---------------------|                      |
  |                      | UPDATE chat_message  |
  |                      | (content +           |
  |                      |  finish_reason=stop) |
  |                      |--------------------->|
  | SSE: message_complete|                      |
  | {message_id,         |                      |
  |  finish_reason}      |                      |
  |<---------------------|                      |
  | SSE: done            |                      |
  |<---------------------|                      |
```