# FinAgentOS Phase 1 — Current Acceptance Summary

**Status**: Phase 1 MVP is end-to-end functional against a real Supabase project and a real GLM-5.1 LLM endpoint. Importer → backend APIs → backend chat SSE → frontend chat MVP have all been smoke-tested with the real stack and committed.

**As of commit**: `e7b97cf` on `main`
**Date**: 2026-06-09

This document is a snapshot, not a spec. The authoritative spec lives in `openspec/changes/fin-agent-os/`. The authoritative project / backend / frontend rules live in `2033_fin_agent/AGENTS.md`, `2033_fin_agent/backend/AGENTS.md`, `2033_fin_agent/frontend/AGENTS.md`. This file just states *what is true today* and *what to consider next*.

---

## 1. What's Done

### Data layer (Supabase)

- **Schema migration** applied: `agents`, `skills`, `verticals`, `mcp_servers`, `agent_skills`, `agent_mcps`, `vertical_skills`, `vertical_mcps`, `chat_sessions`, `chat_messages`, `model_configs`. `chat_sessions.user_id` is `UUID NULL` for Phase 2 backfill. Secrets stored plain in `TEXT` with documented disclosure policy (responses never return plaintext `api_key`; see backend/AGENTS.md "Secret Storage Policy").
- **Importers** parse the upstream `anthropics/financial-services` repo via `UPSTREAM_PLUGINS_PATH` (read-only) and write to Supabase via `--apply`. Live `--apply` against the real Supabase project produced **10 agents, 7 verticals, 55 skills, 11 MCP servers**, plus association rows (`agent_mcps` writes only `matched + aliased` candidates; unmatched aliases are reported and skipped, never persisted).

### Backend (FastAPI on `:8000`)

- **`/health`** returns `{"status":"ok","service":"fin-agent-os-backend"}`. Intentionally does not touch Supabase or the LLM, so a downstream outage cannot mark the service unhealthy.
- **Read-only catalog APIs** — `GET /api/agents`, `GET /api/agents/{slug}`, `GET /api/verticals`, `GET /api/verticals/{slug}`, `GET /api/mcp-servers`, `GET /api/mcp-servers/{id}`. List endpoints expose `has_api_key` (boolean); detail endpoints expose `masked_api_key` (last-4-only); plaintext `api_key` is never returned.
- **MCP management write APIs** — `POST /api/mcp-servers`, `PUT /api/mcp-servers/{id}` — `X-Admin-Token` guarded.
- **Model config APIs** — `GET /api/model-configs`, `GET /api/model-configs/default`, `POST /api/model-configs` (admin), `PUT /api/model-configs/{id}` (admin), `POST /api/model-configs/{id}/test-connection` (admin). `is_default = true` is exclusive (only one default). Secret policy identical to `mcp_servers`.
- **Real default model config** — a `zhipu-coding-glm-51` config pointing at `https://open.bigmodel.cn/api/paas/v4` was created via `POST /api/model-configs` with `is_default=true` and validated via `test-connection` against the real GLM-5.1 endpoint (Gate 7A).
- **MCP adapter layer** — `mcp-use` integrated; per-session lazy initialization; graceful degradation on unreachable MCP servers. **Not yet wired into the chat execution path** (see Option A below).
- **Chat session CRUD + SSE streaming engine** — `POST /api/sessions`, `GET /api/sessions`, `GET /api/sessions/{id}`, `POST /api/sessions/{id}/messages` (SSE). Real LLM call goes through the model-config service boundary; the engine emits `message_start → token* → message_complete → done` events; errors are emitted as `error` events with RFC 7807-style payloads. **`DELETE /api/sessions/{id}` deliberately does not exist** — Phase 1 sessions are anonymous, so a public delete would let any caller wipe any session.
- **Backend chat SSE manual smoke** against the real GLM-5.1 endpoint — session `e3a36e60-f90c-44e9-8b50-79c920f73f15`, assistant message `1a2a65a6-...`, 52 tokens emitted, `finish_reason=stop`, no API-key leak in headers / SSE payload / log lines.

### Frontend (Next.js 14 on `:3000`)

- **Chat MVP integration** — `app/agents/page.tsx` (server component, lists agents, `force-dynamic`), `app/agents/[slug]/chat/page.tsx` (client component, creates session and streams), `lib/api/client.ts` (typed `fetch` wrapper with RFC 7807 unwrap), `lib/api/types.ts` (hand-written contract mirror), `lib/chat/sse-parser.ts` (UTF-8-safe `ReadableStream` consumer split on `\n\n`), `stores/chat-store.ts` (Zustand store). **No DELETE UI, no `tool_call` / `tool_result` UI, no admin token in the chat surface.**
- **Real Chat SSE browser QA** — Playwright drove the live UI against the real backend + real GLM-5.1: `/agents` rendered all 10 agents, `pitch-agent` chat sent a Chinese prompt, assistant tokens streamed in, reload restored persisted messages via `GET /api/sessions/{id}`, 0 console errors.
- **Frontend contract hygiene** — Package manager standardized on **npm** (authoritative lockfile `package-lock.json`); frontend env is **exactly one var (`NEXT_PUBLIC_BACKEND_URL`)** with `NEXT_PUBLIC_SUPABASE_*`, `SUPABASE_SERVICE_KEY`, `LLM_API_KEY`, and `INTERNAL_ADMIN_TOKEN` explicitly forbidden from the frontend bundle.

---

## 2. Key Commits

In chronological order:

| Commit | What |
|---|---|
| `b67ebaa` | Phase 1 Supabase initial schema migration |
| `f313c7f` | Task 2a — agent parser (parse-only) |
| `d3db520` | Task 3a — vertical / skill / MCP parsers + association dry-run |
| `947ae02` | Task 3b — Supabase writer + `--apply` for all 5 CLIs |
| `96bafa8` | Task 4 — backend FastAPI scaffold (config, Supabase boundary, admin dep, `/health`, smoke) |
| `573343b` | Task 4 follow-up — add `SUPABASE_DB_URL` (optional, migration-only) |
| `877bd81` | Task 5 — read-only APIs (agents / verticals / MCPs) |
| `0e6da89` | Task 6 — MCP adapter layer |
| `49aacad` | Task 8 — `model_configs` API + LLM test connection |
| `08252cc` | Gate 7A — model config connection endpoint test against real GLM-5.1 |
| `38bbcc9` | Refactor — `LLM_*` env vars made legacy optional now that `model_configs` is source of truth |
| `f54d494` | Config contract cleanup v2 — separate runtime / importer / migration / legacy env |
| `1da0e23` | Auth — lock down `INTERNAL_ADMIN_TOKEN` contract as Phase 1 operator-only guard |
| `2576c3d` | Docs — align AGENTS.md / tasks.md with current LLM + upstream-path contract |
| `e4b9e19` | Task 7 — chat session CRUD + SSE streaming engine |
| `436d683` | Task 7 fix — keep runtime model config behind service boundary |
| `02803b6` | Task 7 fix — keep SSE assistant message identity stable |
| `f29213f` | Task 7 handoff doc (`docs/handoffs/task-7-chat-backend-handoff.md`) |
| `351dbf3` | Frontend chat MVP integration with backend SSE |
| `e7b97cf` | Frontend contract hygiene (npm + env vars + README rewrite + `/agents` force-dynamic) |


---

## 3. Runtime Architecture

```
┌──────────────┐  HTTPS   ┌──────────────────┐  PostgREST  ┌────────────┐
│  Next.js 14  │ ───────▶ │  FastAPI         │ ──────────▶ │  Supabase  │
│  (Vercel)    │          │  (Fly.io Tokyo)  │             │  Postgres  │
└──────────────┘          └────────┬─────────┘             └────────────┘
                                   │
                                   │ OpenAI-compatible HTTP
                                   ▼
                          ┌──────────────────┐
                          │  LLM provider    │
                          │  (GLM-5.1 today, │
                          │   any compatible)│
                          └──────────────────┘
```

**Hard runtime rules** (enforced by docs + code review):

- The **frontend talks only to FastAPI**. No `@supabase/supabase-js` dependency, no direct Supabase URL, no model API key in the bundle.
- **FastAPI is the only thing that talks to Supabase and to the LLM provider.** All credentials live as server-side deployment secrets.
- The **frontend does NOT talk to Supabase.** Phase 2 Supabase Auth will add the anon key for the auth client only — never the service-role key.
- **`model_configs` is the source of truth for the LLM endpoint.** Backend reads the default via `model_config_service` / the LLM adapter boundary. Hardcoding provider/model names in runtime code is forbidden.
- The **importer is an offline operator path**, not part of the FastAPI runtime. It reads from the upstream `anthropics/financial-services` repo and writes to Supabase.
- **`UPSTREAM_PLUGINS_PATH`** is an importer-only env var — the FastAPI runtime never reads it.
- **`SUPABASE_DB_URL`** is a migration-only env var (used to apply SQL migrations) — the FastAPI runtime never reads it.
- **`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`** are *legacy optional* env vars kept only for pre-Task-8 back-compat with dev `.env` files and out-of-lifecycle scripts. New runtime code paths must route through `model_configs`, not these env vars.

---

## 4. Auth / Security Boundary (Phase 1)

- **No end-user authentication.** No login UI. No Supabase Auth. No JWT validation. No RLS.
- **Chat endpoints are public and anonymous** — `POST /api/sessions`, `GET /api/sessions`, `GET /api/sessions/{id}`, `POST /api/sessions/{id}/messages`. Sessions have no `user_id` in Phase 1; `chat_sessions.user_id` is `UUID NULL` precisely so Phase 2 can backfill ownership without a migration break.
- **Admin / write endpoints are guarded by `X-Admin-Token`** — `POST /api/import/*`, `POST /api/mcp-servers`, `PUT /api/mcp-servers/{id}`, `POST /api/model-configs`, `PUT /api/model-configs/{id}`, `POST /api/model-configs/{id}/test-connection`. The header is compared against the server-side `INTERNAL_ADMIN_TOKEN` env var via `hmac.compare_digest`.
- **`INTERNAL_ADMIN_TOKEN` contract** (locked down in `1da0e23`):
  - Phase 1 only. Deleted in Phase 2.
  - Internal operator/admin API guard. Not a user-auth mechanism. Not OAuth, not JWT, not RBAC.
  - Server-side deployment secret. Lives in `backend/.env` / Fly.io secrets. Shared out-of-band with operators only.
  - **Must not appear in the frontend bundle, the chat UI, or any public end-user route.** Any operator/admin UI that lets a human paste it is an internal operator-only tool, not a public end-user surface.
- **No frontend secret exposure.** The Phase 1 frontend bundle holds only `NEXT_PUBLIC_BACKEND_URL`. `SUPABASE_SERVICE_KEY`, `LLM_API_KEY`, model provider keys, and `INTERNAL_ADMIN_TOKEN` are all server-side only and never reach the browser.
- **Phase 2 replacement**: Supabase Auth (JWT in `Authorization: Bearer <token>`) + role-based access control + Postgres RLS. `INTERNAL_ADMIN_TOKEN` and `require_admin_token` are removed. Existing `chat_sessions.user_id NULL` columns are backfilled with the now-authenticated user.

---

## 5. Verification Evidence

| Stage | Command / Action | Result |
|---|---|---|
| Backend tests | `pytest` under `backend/` (covers importers, read APIs, model configs, chat sessions + SSE engine) | green at each completed task commit; live `--apply` post-run row counts in Supabase match `import_all.py` reported counts exactly |
| Backend lint | `ruff check backend/` | clean |
| OpenSpec | `openspec validate fin-agent-os --strict` | passes |
| Gate 7A | `POST /api/model-configs/{id}/test-connection` against the real GLM-5.1 endpoint (`https://open.bigmodel.cn/api/paas/v4`) | 200 OK, real completion returned, no secret leak (`08252cc`) |
| Real Chat SSE manual smoke | direct `POST /api/sessions/{id}/messages` against backend on `:8001` with real GLM-5.1 | session `e3a36e60-...`, 52 tokens, `finish_reason=stop`, no API-key leak |
| Frontend lint | `npm run lint` | clean |
| Frontend typecheck | `npm run typecheck` (`tsc --noEmit` strict) | clean |
| Frontend tests | `npm run test` (Vitest) | 7/7 passed (SSE parser unit tests) |
| Frontend build | `npm run build` | success; `/agents` correctly marked `ƒ (Dynamic)` |
| Real browser QA | Playwright against `localhost:3000` + backend on `:8001` + real GLM-5.1 | `/agents` lists 10 agents; `pitch-agent` chat streams Chinese assistant response; reload restores persisted messages; 0 console errors; network shows `POST /api/sessions` 201 → `POST .../messages` 200 SSE → `GET /api/sessions/{id}` 200 |

---

## 6. Known Limitations

These are deliberate Phase 1 scope choices, not bugs. They are listed so the next iteration can decide which to lift.

- **Anonymous sessions.** `chat_sessions.user_id` is always `NULL` in Phase 1. Any caller can create / read any session. Acceptable because Phase 1 is internal-B2B-MVP; not acceptable for public launch.
- **No session URL / history restore.** `sessionId` lives only in the page-local React state. Reloading the chat page creates a new session (the previous session row stays in Supabase but the UI does not surface it). Putting `sessionId` into the URL and listing prior sessions in a sidebar is a Phase 1.x polish.
- **No `DELETE /api/sessions/{id}` and no delete UI.** Removed deliberately in `436d683` because Phase 1 sessions are anonymous. Will re-introduce behind Phase 2 auth + ownership check.
- **No end-user auth / RBAC / RLS.** Phase 2 work — Supabase Auth + JWT + RBAC + Postgres RLS.
- **No `tool_call` / `tool_result` rendering in chat, and no backend tool execution in the chat path.** The MCP adapter layer (Task 6) is built and unit-tested but is not yet invoked by the chat engine; the LLM today gets no tools, so it can only produce text. Adding tool execution is Option A below.
- **No context-window / token-budget management.** The chat engine sends the full message history every turn. Long sessions will eventually hit the model's context limit. Needs a windowing or summarization strategy before sessions get long.
- **No pagination on `GET /api/sessions`.** Returns all sessions in one response. Fine at MVP scale, painful at production scale.
- **No production deployment proof yet.** Backend is `Dockerfile`-ready and has a `fly.toml` targeting `nrt` (Tokyo); frontend is `next build`-ready for Vercel. Neither has been deployed end-to-end against the real Supabase + real LLM and exercised by a real client browser. Option C below.
- **Pyright is not yet integrated into the backend CI loop.** `pyright` is declared as a backend dev dependency but no CI gate enforces it. Should be added to the pre-commit / CI gate before Phase 2.

---

## 7. Recommended Next Options

Three plausible next moves. Pick one to commit to next; do not parallelize all three.

### Option A — MCP tool-call integration into chat

**Why**: The MCP adapter layer (Task 6) is built but unused; until the chat engine actually invokes tools, the agents are just "GLM-5.1 with a system prompt." The product promise (pitch decks, comps, earnings notes) depends on tool execution.

**Risks**:
- LLM tool-call format varies by provider; have to keep `mcp-use`'s OpenAI bridge happy across providers.
- Per-session MCP authentication: most upstream MCP servers require an API key the operator must provide; need a config/storage path that respects the existing secret policy.
- Streaming SSE shape grows (`tool_call`, `tool_result` events the frontend currently does not render).
- Concurrent tool calls + LLM continuation can deadlock if not careful with the stream lifecycle.

**Prerequisite gates**:
- Decide and document the MCP credential storage model (per-MCP `api_key` is already in the schema and admin-API-guarded; need explicit policy for which MCPs Phase 1 actually exercises).
- Pick one MCP target to validate against first — `s_and_p_global_capiq` or a stub server.
- Frontend must add `tool_call` / `tool_result` rendering (currently the SSE parser knows about them but the UI discards them).

**Suggested first task**: wire `mcp_service` into `chat_engine.run_completion`, gated by a single-tool whitelist (e.g. just the first MCP we test against). Emit `tool_call` and `tool_result` SSE events. Backend-only; defer frontend rendering until backend events are stable.

### Option B — Session URL / history restore + frontend polish

**Why**: The MVP works but reloading the chat page silently drops the session, which is the most jarring UX gap from the browser QA. Plus a sidebar list of prior sessions is essentially a 1-day add on top of the existing `GET /api/sessions` endpoint.

**Risks**:
- Putting `sessionId` in the URL forces a decision on shareable URLs (which today let any anonymous caller read any anonymous session — a Phase-1-scope-acceptable but worth-noting consequence).
- Sidebar pagination becomes necessary as session count grows; should ship pagination at the same time so we do not regress later.
- Pure frontend churn — no real product capability added, just polish.

**Prerequisite gates**:
- None — purely frontend + an optional `GET /api/sessions?limit=&cursor=` if we want to ship pagination at the same time.

**Suggested first task**: move `sessionId` into the URL (`/agents/[slug]/chat/[sessionId]`) and have the chat page hydrate from `GET /api/sessions/{id}` instead of always creating a new one. Add a sidebar `<SessionList>` powered by `GET /api/sessions`.

### Option C — Deployment / production readiness pass

**Why**: Everything works locally against a real Supabase + real GLM-5.1, but nothing has been deployed end-to-end. Until the backend is on Fly.io (Tokyo) and the frontend is on Vercel with real env vars, we cannot prove the architecture in production conditions (CORS, cold starts, SSE through Vercel's edge, Supabase RLS-off-but-PostgREST-on under real-network latency).

**Risks**:
- SSE through Vercel + Fly.io has edge-case buffering issues that only show up under real network conditions.
- First production deploy will surface env-var typos, missing secrets, and CORS misconfigurations that local dev hides.
- Cold-start latency on Fly.io scale-to-zero can break the first user's chat.
- No monitoring / alerting / log aggregation in place yet — we will be debugging production blind on the first issue.

**Prerequisite gates**:
- Real Supabase + real LLM env vars staged as Fly.io / Vercel secrets.
- CORS allowlist decided (single Vercel domain in Phase 1 is fine).
- Decide on log destination (Fly.io tail is fine for MVP; structured JSON logs already in place).
- Decide on a basic uptime/health monitor (even `curl /health` from a cron is acceptable for Phase 1).

**Suggested first task**: `fly launch` (or `fly deploy` against the existing `fly.toml`) into `nrt`, set the production secrets, smoke `/health` and one real chat session via Vercel preview → Fly backend → Supabase → GLM-5.1. Capture the verification trace as a Phase 1 deployment handoff doc.

---

## 8. Decision Hook

When the next iteration starts, the first message should pick one of A / B / C above (or explicitly defer all three for a different priority). Each option's "Suggested first task" is intentionally scoped to one PR worth of work.
