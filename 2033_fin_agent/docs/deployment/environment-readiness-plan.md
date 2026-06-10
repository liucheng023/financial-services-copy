# FinAgentOS — Environment Readiness Plan

**Status**: planning only. No deployment is executed by this document.
**As of commit**: `0ff2f9b` on `main`
**Scope**: define the *next* environment we will create (testing), the
target topology testing must mirror (production), and the explicit policy
for the temporarily shared non-production data source. No business
features. No MCP wiring. No new Phase 1 scope.

This document is a snapshot, not a spec. Authoritative rules still live in
`2033_fin_agent/AGENTS.md`, `2033_fin_agent/backend/AGENTS.md`,
`2033_fin_agent/frontend/AGENTS.md`, and
`openspec/changes/fin-agent-os/`. This file describes *which environments
exist*, *which one we build next*, and *what must be true before we ship
either of them*.

---

## 1. Environment Strategy Summary

- **development / local** — already exists. Validated end-to-end against a
  real Supabase project and the real GLM-5.1 endpoint
  (`https://open.bigmodel.cn/api/coding/paas/v4`). Captured in
  `docs/handoffs/phase-1-current-acceptance.md`.
- **testing** — the next environment we will create. Hosted on Vercel
  (frontend) and Fly.io (backend, region `nrt`). Used for internal QA
  against a deployed stack before any external user sees the product.
- **production** — created **only after testing passes**. Topology is
  identical to testing; configuration is isolated.
- **staging / pre-production** — **not created now**. Slot is reserved in
  the matrix and in env-var naming so we can add it later without
  re-architecting. Activation triggers are listed in §9.
- **Topology parity, config isolation**: testing and production run the
  same Dockerfile, the same `fly.toml` shape, the same Next.js build, and
  the same env-var contract. Only the *values* differ.
- **Initially shared non-production data source**: development/local and
  testing **may** point at the same non-production Supabase project,
  object storage bucket, and `model_configs` rows during early testing.
  This is a deliberate efficiency choice for Phase 1, not the
  long-term architecture. The policy and risks are in §4.

---

## 2. Environment Matrix

| environment | purpose | frontend | backend | data source | secrets | CORS | users | deployment trigger | data source isolation |
|---|---|---|---|---|---|---|---|---|---|
| development / local | day-to-day dev, fast feedback, real-stack smoke | local Next.js (`npm run dev`, `:3000`) | local FastAPI (`uvicorn --reload`) or local Docker (`python:3.11-slim`, port `:8001` if `:8000` is taken) | **may** share the same non-production Supabase + object storage + `model_configs` as testing | `backend/.env` only (gitignored); never committed | `CORS_ORIGINS=http://localhost:3000` (default) | developers only | manual (`uvicorn` / `docker run`) | **not isolated from testing in Phase 1** — see §4 |
| testing | internal QA against deployed stack; SSE / cold-start / CORS smoke under real network | Vercel project `fin-agent-os-frontend-testing` (or equivalent), preview-or-prod deployment of `main` | Fly.io app `fin-agent-os-backend-testing`, region `nrt`, single machine acceptable | **may** share the same non-production Supabase as development/local initially | Fly.io secrets (backend) + Vercel project env vars (frontend, public only) | `CORS_ORIGINS` = the testing Vercel URL, plus `http://localhost:3000` only if local→testing-backend smoke is needed | internal QA only; no external users | manual `fly deploy` + Vercel deployment of `main` (or a `testing` branch if we adopt one) | **not isolated from development/local in Phase 1** — see §4 |
| production | live B2B traffic | Vercel project `fin-agent-os-frontend` (or equivalent), production deployment | Fly.io app `fin-agent-os-backend`, region `nrt` (add regions later per `backend/AGENTS.md`) | **decision required before launch** — independent production Supabase strongly preferred; see §8 | Fly.io secrets (backend) + Vercel project env vars (frontend); rotated independently of testing | `CORS_ORIGINS` = production frontend URL only; no `localhost`, no `*` | real B2B users | tagged release (`vX.Y.Z`) → manual `fly deploy` + Vercel production promote | **MUST** be isolated from non-production by launch (see §8) |
| staging / pre-production | **deferred** — release-candidate validation before production | not provisioned | not provisioned | not provisioned | not provisioned | n/a | n/a | n/a | n/a |

Naming conventions reserved (do not create the resources now):
- Fly apps: `fin-agent-os-backend-staging`
- Vercel project: `fin-agent-os-frontend-staging`
- Supabase project: `fin-agent-os-staging`

---

## 3. Target Topology (testing and production, identical shape)

```
            ┌──────────────────────┐
            │  Browser (B2B user)  │
            └──────────┬───────────┘
                       │ HTTPS only
                       ▼
            ┌──────────────────────┐
            │  Vercel              │
            │  Next.js frontend    │   only env var consumed:
            │                      │   NEXT_PUBLIC_BACKEND_URL
            └──────────┬───────────┘
                       │ HTTPS only (fetch + SSE)
                       │ never talks to Supabase directly
                       │ never talks to LLM directly
                       ▼
            ┌──────────────────────┐
            │  Fly.io (nrt)        │
            │  FastAPI backend     │
            │  Dockerfile          │
            │  port 8000 internal  │
            └────┬─────────────┬───┘
                 │             │
                 ▼             ▼
        ┌────────────┐   ┌──────────────────┐
        │ Supabase   │   │ LLM provider     │
        │ (Postgres  │   │ (GLM-5.1 by      │
        │  + Storage)│   │  default, any    │
        │            │   │  OpenAI-compat.) │
        └────────────┘   └──────────────────┘

(offline / operator path, NOT in the request path)
            ┌──────────────────────┐
            │  Operator workstation│
            │  python -m            │
            │  app.importers.*      │
            └──────────┬───────────┘
                       │ reads $UPSTREAM_PLUGINS_PATH (local FS)
                       │ writes to Supabase via service key
                       ▼
                  Supabase
```

Rules baked into this topology (already enforced by code/AGENTS.md, restated
here so the deployment plan cannot drift from them):

- **Frontend only talks to FastAPI.** No Supabase client, no LLM SDK, no
  admin token in the browser. (`frontend/AGENTS.md`.)
- **FastAPI is the only thing that talks to Supabase and the LLM.** All LLM
  endpoint / api_key resolution goes through the `model_configs` Supabase
  table via the model-config service boundary; `LLM_*` env vars are legacy
  back-compat only and are NOT in the runtime path. (`backend/AGENTS.md`.)
- **`model_configs` is the LLM source of truth** at runtime. The Phase 1
  default is a `zhipu-coding-glm-51` row with `is_default=true` pointing at
  `https://open.bigmodel.cn/api/coding/paas/v4`.
- **Importer is an offline / operator path.** It reads
  `$UPSTREAM_PLUGINS_PATH` from the operator's local filesystem and writes
  to Supabase via the service key. It is not part of the request path and
  is not deployed as part of either Vercel or Fly.io.

---

## 4. Shared Non-production Data Source Policy

### What is shared

In early Phase 1, **development/local and testing may point at the same
non-production resources**:

- the same Supabase project (Postgres schema, `agents`, `verticals`,
  `skills`, `mcp_servers`, `model_configs`, `chat_sessions`,
  `chat_messages`)
- the same Supabase Storage bucket (if/when files are added)
- the same `model_configs` rows — in particular, the single
  `is_default=true` row that the chat engine resolves on every request

### Why it is acceptable for Phase 1

- The project is internal MVP. No external customer data, no PII, no real
  customer-bound chat history.
- The non-production data set is small and is intentionally reproducible
  via the importer (`python -m app.importers.import_all`) — losing it is
  inconvenient, not catastrophic.
- Standing up two non-production Supabase projects and keeping their
  `model_configs` / `mcp_servers` in sync by hand would be more failure
  surface than it removes during Phase 1.

This is an **efficiency choice**, not a final architecture. Production
**must** revisit this — see §8.

### Treatment rules (mandatory while shared)

- The shared Supabase project MUST be named explicitly as
  `fin-agent-os-nonprod` (or equivalent) in dashboards, Fly secrets, and
  Vercel env vars. Never label it "shared" or "prod" or leave it unnamed.
- No real customer-sensitive data lands in the shared project. Synthetic
  test inputs only.
- Testing smoke is allowed to create rows in `chat_sessions` /
  `chat_messages`. These are non-production artifacts and may be
  truncated.
- `import_all`, `apply` re-runs, `POST /api/model-configs`,
  `PUT /api/model-configs/{id}`, `POST /api/mcp-servers`, and
  `PUT /api/mcp-servers/{id}` against the shared project affect
  **both** development/local and testing simultaneously. Treat them as
  shared-state writes.
- Before any testing smoke, record the current default `model_config`
  (id, provider, model, base_url, masked api_key) so that a
  dev-side change can be detected if smoke fails unexpectedly.

### Risks of the shared model

- A developer running `import_all --apply` locally changes the rows the
  testing environment reads.
- A testing QA run pollutes the dev developer's session list and chat
  history.
- An admin mistake (`PUT /api/model-configs/{id}` with a wrong `base_url`
  or `api_key`) has a wider blast radius — both environments break at
  once.
- We cannot validate the production-data-isolation assumption (RLS-off
  but service-key-only access, importer-only writes, etc.) until we
  actually split the data source. Sharing hides this whole class of bug.

### Mitigations

- The shared Supabase project is **explicitly named non-production** so
  no one can confuse it with production later.
- Destructive operations (`TRUNCATE`, `DELETE FROM chat_sessions`,
  schema drops, raw SQL admin actions) require explicit human
  confirmation; never automated.
- The default `model_config` snapshot is recorded immediately before
  every testing smoke run, so an unexpected change is caught fast.
- The creation of production (see §8) **must** revisit the data-source
  isolation decision. Sharing across environments is forbidden the
  moment production exists.
- The first real-customer demo or first external-user testing event
  must trigger a re-evaluation of the data-source split, even if
  production has not been built yet. Treat "we are about to show this
  to a real outsider" as a forcing function.

---

## 5. Testing Environment Plan

### Hosting

- **Frontend** — Vercel project (suggested name
  `fin-agent-os-frontend-testing`). Hosts the existing Next.js 14 App
  Router build. No changes to `next.config.mjs` required for testing.
- **Backend** — Fly.io app (suggested name
  `fin-agent-os-backend-testing`), region `nrt` (Tokyo). Uses the
  existing `backend/Dockerfile` and the existing `backend/fly.toml`
  shape (`internal_port = 8000`, health check on `GET /health`,
  `auto_stop_machines = "stop"`, `auto_start_machines = true`,
  `min_machines_running = 0`).
  - Note: `fly.toml` currently hardcodes `app = "fin-agent-os-backend"`.
    Testing deployment must either deploy via `fly deploy --app
    fin-agent-os-backend-testing` or use a per-environment `fly.toml`
    copy. This is a deploy-time choice, not a code change for Phase 1.

### Required environment variables

**Frontend (Vercel, testing project)**

| Var | Value | Notes |
|---|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | `https://<testing-fly-backend-url>` | The only frontend env var consumed in Phase 1. Public by design (it ships in the JS bundle). |

**Backend runtime (Fly.io secrets, testing app)**

| Var | Purpose |
|---|---|
| `SUPABASE_URL` | Non-production Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Non-production Supabase service-role key. **Server-side only.** Never exposed to the browser. |
| `INTERNAL_ADMIN_TOKEN` | Phase 1 internal operator/admin API guard. Server-side deployment secret. **Not a user-auth mechanism.** See `backend/AGENTS.md`. |
| `CORS_ORIGINS` | Comma-separated allowlist; for testing this is the Vercel testing URL (plus `http://localhost:3000` only if local→testing-backend smoke is required). |
| `LOG_LEVEL` | `INFO` (default in `fly.toml`). |

**Migration-only (operator workstation, not a Fly secret)**

| Var | Purpose |
|---|---|
| `SUPABASE_DB_URL` | Used by `psql` / `supabase` CLI for schema migrations. The FastAPI runtime does **not** read it. |

**Importer-only (operator workstation, not a Fly secret)**

| Var | Purpose |
|---|---|
| `UPSTREAM_PLUGINS_PATH` | Absolute path to the upstream `plugins/` directory on the operator's machine. Used by `python -m app.importers.import_*`. The FastAPI runtime does **not** read it. |

**Legacy optional (deliberately not set in testing)**

| Var | Status |
|---|---|
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | **Not used at runtime.** The runtime LLM source of truth is the `model_configs` Supabase table via the model-config service boundary. Setting these in testing creates the illusion of a runtime path that does not exist; do not set them. |

### Forbidden frontend env vars (testing and beyond)

The Vercel testing project MUST NOT define any of:

- `SUPABASE_SERVICE_KEY` — server-side secret; browser exposure is a
  full-trust compromise.
- `INTERNAL_ADMIN_TOKEN` — operator-only secret; browser exposure lets
  any visitor hit admin endpoints.
- `LLM_API_KEY` (or any provider api_key) — model api_keys live in
  `model_configs` rows on the backend; the frontend never sees them.
- `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` —
  intentionally absent in Phase 1. The frontend has no Supabase client;
  it only talks to FastAPI. Adding these would silently create a
  second data path the rest of the architecture does not account for.

---

## 6. CORS Strategy

- **Testing backend `CORS_ORIGINS`**: the testing Vercel URL is the
  primary entry. `http://localhost:3000` may be added only if
  local→testing-backend smoke is part of the QA loop; remove it once it
  is no longer needed.
- **Production backend `CORS_ORIGINS`**: production frontend URL only.
  No `localhost`. No `*`. No testing URL.
- **Wildcard `*`**: forbidden in testing and production unless an
  explicit written justification is recorded in this document. Phase 1
  has none.
- **Implementation**: backend reads `CORS_ORIGINS` as a comma-separated
  string in `app/core/config.py` (`Settings.cors_origin_list`) and feeds
  it to `CORSMiddleware.allow_origins` in `app/main.py`. No code change
  needed to switch environments — only the env var value differs.

---

## 7. Testing Smoke Checklist

Run after every testing deploy. All items must pass before the deploy is
declared green. Capture evidence (response bodies, screenshots, network
trace) in a deploy handoff doc.

Backend (call the testing Fly URL directly):

- [ ] `GET /health` → 200
- [ ] `GET /api/agents` → 200, returns 10 agents
- [ ] `GET /api/model-configs` → 200, contains exactly one row with
  `is_default = true`; that row's `api_key` field is **not** plaintext
  (either omitted, returned as `has_api_key: true`, or masked as
  `****<last4>`)
  - If `GET /api/model-configs/default` is exposed at deploy time, hit
    it as well and confirm the same masking rule applies. (Phase 1 may
    not expose this route; do not fail the smoke if it 404s — the
    `GET /api/model-configs` assertion above is the source of truth.)

Frontend (open the testing Vercel URL in a real browser):

- [ ] `/agents` loads and lists 10 agents (no client-side error, no
  stale-build fallback — page is marked `ƒ (Dynamic)` in `next build`
  already)
- [ ] Open `pitch-agent`, send one short Chinese message
- [ ] SSE stream observed in DevTools Network: event sequence is
  `message_start → token (1+) → message_complete → done`
- [ ] `message_start.message_id` equals `message_complete.message_id`
- [ ] `GET /api/sessions/{id}` (called from the page or hit directly)
  returns the session with both the user message and the assistant
  message persisted
- [ ] Browser console: 0 errors, 0 warnings related to the app
- [ ] Browser JS bundle and Network requests contain **no** secrets —
  no `SUPABASE_SERVICE_KEY`, no `INTERNAL_ADMIN_TOKEN`, no LLM
  `api_key`, no Supabase service URL embedded in client code
- [ ] Fly backend logs for the smoke window contain **no** secrets —
  no plaintext api_key, no service key, no admin token

If any item fails, stop and follow §10.

---

## 8. Production Promotion Gate

Before creating the production environment, the following decisions must
be made and recorded:

- **Data source isolation**:
  - Will production use an **independent** production Supabase project
    (strongly preferred), or temporarily share the non-production
    project (strongly discouraged for production)?
  - If independent: plan the schema migration apply order
    (`SUPABASE_DB_URL` against the production project), the importer
    re-run (`python -m app.importers.import_all --apply` against the
    production project), and a safe copy of `model_configs` /
    `mcp_servers` rows including api_key handling (api_keys must be
    re-entered, **not** copied out of the non-production project in
    plaintext through any intermediate machine).
- **Secret rotation**:
  - Generate a fresh `INTERNAL_ADMIN_TOKEN` for production. Never reuse
    the non-production value.
  - Generate / collect production-only LLM api_keys for the production
    `model_configs` rows. Never reuse non-production keys.
- **CORS**:
  - Decide the production frontend canonical URL.
  - Set production backend `CORS_ORIGINS` to that URL only. No
    `localhost`. No testing URL.
- **App naming**:
  - Production Fly app name (`fin-agent-os-backend`).
  - Production Vercel project name (`fin-agent-os-frontend`).
  - Production frontend domain (custom domain decision).
- **Smoke parity**: production smoke checklist is the same as §7,
  executed against the production URLs and the production Supabase
  project.
- **Non-production cleanup decision**: decide whether to truncate
  non-production `chat_sessions` / `chat_messages` and which rows in
  `model_configs` / `mcp_servers` are kept after the split. Document the
  outcome; do not silently delete.

Production is not "deployed" — it is **created**, then promoted to once
testing and the above gates pass.

---

## 9. Staging / Pre-production — Deferred

Staging is **not** created in Phase 1. Reserve the names only (see §2).

Re-evaluate when any of the following becomes true:

- Real external users are about to be onboarded.
- A customer demo requires a stable release-candidate version that does
  not move under the demo's feet.
- Release frequency increases to the point where testing is
  continuously moving and there is no quiet window to validate a
  release candidate.
- Multiple developers ship concurrently and need a shared QA target
  that is not a personal local.
- A risky schema migration is planned (irreversible drops, large
  backfills, breaking column rename) and needs a non-production rehearsal
  on production-shape data.
- Production data is fully separated from non-production and a
  release-candidate validation gate is required before promoting code to
  production.

When activated: stand up `fin-agent-os-backend-staging` (Fly.io, `nrt`),
`fin-agent-os-frontend-staging` (Vercel), and a `fin-agent-os-staging`
Supabase project. Apply §6 CORS rules and §7 smoke checklist against the
staging URLs.

---

## 10. Deployment Stop Conditions

If **any** of the following occurs during or after a deploy, stop and
report. Do not "fix forward" without an explicit go-ahead.

- A secret (`SUPABASE_SERVICE_KEY`, `INTERNAL_ADMIN_TOKEN`, any LLM
  `api_key`) appears in: Fly logs, Vercel logs, frontend JS bundle, a
  browser Network response, or any committed file.
- CORS blocks the frontend from calling the backend (browser console
  shows a CORS error, or `Access-Control-Allow-Origin` is missing /
  wrong).
- SSE response is buffered — the client receives the full response in
  one chunk after the LLM finishes, instead of token-by-token streaming.
  Likely Vercel edge / Fly proxy buffering or wrong `Content-Type` /
  headers.
- Fly backend cannot reach Supabase (DNS failure, 401 from Supabase,
  service key wrong, project paused).
- Backend cannot reach the LLM provider (timeout, 401, wrong base_url,
  wrong model name, provider rate-limited).
- The `model_configs` table contains zero rows with `is_default = true`,
  or the default row's `base_url` / `api_key` is wrong for the
  environment.
- Vercel env vars misconfigured (`NEXT_PUBLIC_BACKEND_URL` points at
  localhost / wrong host / non-HTTPS / trailing slash issues).
- `GET /health` fails or returns non-200 after the deploy settles.
- Testing smoke unexpectedly creates rows in a data source it should not
  be touching (e.g., production Supabase URL accidentally configured in
  testing secrets).

For every stop, capture: the failing check, the request/response or log
excerpt, the env vars in effect (names only, never values), and the
commit hash deployed.

---

## 11. Open Questions for Human Confirmation

Before we execute the testing deploy, the operator must confirm:

1. **Vercel project name and team/org** for the testing frontend.
2. **Fly.io organization and app name** for the testing backend
   (default suggestion: `fin-agent-os-backend-testing`, region `nrt`).
3. **Shared non-production Supabase project URL and service-role key**
   (the same project that local dev currently uses, or a fresh one) —
   and confirmation that it is explicitly named non-production.
4. **`INTERNAL_ADMIN_TOKEN` for testing** — whether to reuse the local
   dev value (acceptable for shared non-production) or generate a fresh
   one. Either way, it is set as a Fly secret, never committed.
5. **Testing CORS allowlist** — final Vercel testing URL, plus whether
   `http://localhost:3000` should be included.
6. **Whether to deploy on every push to `main`, on a `testing` branch,
   or only manually.** Phase 1 default: manual.
7. **Whether `GET /api/model-configs/default` is exposed in the deployed
   backend**, so the smoke checklist can target the right route.
8. **Acceptance of the shared-data-source risks in §4** as the Phase 1
   working assumption until production is created.

No deploy action is taken until items 1-8 are answered in writing.
