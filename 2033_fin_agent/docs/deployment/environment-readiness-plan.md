# FinAgentOS — Environment Readiness Plan

**Status**: planning only. No deployment is executed by this document.
**As of**: ADR 0001 / commit `2bc0aad` on `main`
**Scope**: define the *next* environment we will create (testing), the
**CI/CD orchestration** that creates it (GitHub Actions), the target
topology testing must mirror (production), and the explicit policy for
the temporarily shared non-production data source. No business features.
No MCP wiring. No new Phase 1 scope. **No GitHub Actions workflow file
is created by this document.**

This document is a snapshot, not a spec. Authoritative rules still live
in `2033_fin_agent/AGENTS.md`, `2033_fin_agent/backend/AGENTS.md`,
`2033_fin_agent/frontend/AGENTS.md`, and
`openspec/changes/fin-agent-os/`. This file describes *which
environments exist*, *which one we build next*, *how it is built (CI/CD,
not manual)*, and *what must be true before we ship either of them*.

---

## 1. Environment Strategy Summary

- **development / local** — already exists. Validated end-to-end
  against a real Supabase project and the real GLM-5.1 endpoint
  (`https://open.bigmodel.cn/api/coding/paas/v4`). Captured in
  `docs/handoffs/phase-1-current-acceptance.md`. This is the
  *development* environment, not a deployable target. The developer
  workstation's job is **local development, local testing, and `git
  push` only** — it does **not** run day-to-day deploys to testing or
  production. Routine `vercel deploy` does **not** run on a developer
  workstation; it runs inside GitHub Actions. Ad-hoc `fly deploy` from
  a laptop is reserved for one-time bootstrap or break-glass recovery,
  not for routine deployment (see §4).
- **testing** — the next environment we will create. **The only
  day-to-day deploy control plane for testing is GitHub Actions.**
  Backend is deployed by GitHub Actions to Fly.io (region `nrt`);
  frontend is deployed by GitHub Actions to Vercel. The Vercel and
  Fly.io dashboards are used **only** for one-time app/project
  creation, viewing platform status, and setting required runtime
  env/secrets — they are **not** a deploy trigger for routine work.
  Used for internal QA against a deployed stack before any external
  user sees the product. See ADR
  `docs/architecture/decisions/0001-testing-cicd-control-plane.md`
  for the rationale.
- **production** — created **only after testing passes**. Topology is
  identical to testing; configuration is isolated. Production CI/CD
  reuses the testing workflow shape behind a protected GitHub
  Environment (or a `production` branch / release tag).
- **staging / pre-production** — **not created now**. Slot is reserved
  in the matrix and in env-var naming so we can add it later without
  re-architecting. Activation triggers are listed in §9.
- **Topology parity, config isolation only.** Testing and production
  run the same Dockerfile, the same `fly.toml` shape, the same Next.js
  build, the same env-var contract, and the same CI/CD workflow shape.
  **Only the values differ** — app names, URLs, secrets, CORS allowlists.
- **Initially shared non-production data source.** Development/local
  and testing **may** point at the same non-production Supabase
  project, object storage bucket, and `model_configs` rows during early
  testing. This is a deliberate efficiency choice for Phase 1, not the
  long-term architecture. The policy and risks are in §5.

---

## 2. Environment Matrix

| environment | purpose | frontend | backend | data source | runtime secrets | CI/CD secrets | CORS | users | deployment trigger | data source isolation |
|---|---|---|---|---|---|---|---|---|---|---|
| development / local | day-to-day dev, fast feedback, real-stack smoke | local Next.js (`npm run dev`, `:3000`) | local FastAPI (`uvicorn --reload`) or local Docker (`python:3.11-slim`, port `:8001` if `:8000` is taken) | **may** share the same non-production Supabase + object storage + `model_configs` as testing | `backend/.env` only (gitignored); never committed | none | `CORS_ORIGINS=http://localhost:3000` (default) | developers only | **local development, local testing, and `git push` only** — no day-to-day deploy responsibility; routine `vercel deploy` runs inside GitHub Actions, not locally; ad-hoc `fly deploy` from a laptop is reserved for one-time bootstrap or break-glass | **not isolated from testing in Phase 1** — see §5 |
| testing | internal QA against deployed stack; SSE / cold-start / CORS smoke under real network | Vercel project `fin-agent-os-frontend-testing`, deployment of `main` triggered **only** by GitHub Actions | Fly.io app `fin-agent-os-backend-testing`, region `nrt`, single machine acceptable, deployment of `main` triggered **only** by GitHub Actions | **may** share the same non-production Supabase as development/local initially | **Fly.io secrets only** (backend runtime); Vercel project env vars are limited to `NEXT_PUBLIC_BACKEND_URL` | **GitHub Actions repository secrets**: `FLY_API_TOKEN`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID_TESTING` — **deploy credentials only**, not app runtime secrets | `CORS_ORIGINS` = the testing Vercel URL, plus `http://localhost:3000` only if local→testing-backend smoke is needed | internal QA only; no external users | **GitHub Actions on push to `main`** (sole day-to-day control plane) — backend CI → frontend CI → Fly deploy → Vercel deploy → testing smoke. Vercel / Fly dashboards are used only for one-time bootstrap, status viewing, and runtime secret config. | **not isolated from development/local in Phase 1** — see §5 |
| production | live B2B traffic | Vercel project `fin-agent-os-frontend`, production deployment | Fly.io app `fin-agent-os-backend`, region `nrt` (add regions later per `backend/AGENTS.md`) | **decision required before launch** — independent production Supabase strongly preferred; see §9 | Fly.io secrets (backend) + Vercel env vars (frontend, public only); rotated independently of testing | production-scoped `FLY_API_TOKEN`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID_PRODUCTION` — kept in a separate GitHub Environment with required reviewers | `CORS_ORIGINS` = production frontend URL only; no `localhost`, no `*` | real B2B users | **future protected GitHub Environment** (manual approval) on tag `vX.Y.Z` or `production` branch — **not configured now** | **MUST** be isolated from non-production by launch (see §9) |
| staging / pre-production | **deferred** — release-candidate validation before production | not provisioned | not provisioned | not provisioned | not provisioned | not provisioned | n/a | n/a | n/a | n/a |

Naming conventions reserved (do not create the resources now):
- Fly apps: `fin-agent-os-backend-staging`, `fin-agent-os-backend` (production)
- Vercel projects: `fin-agent-os-frontend-staging`, `fin-agent-os-frontend` (production)
- Supabase projects: `fin-agent-os-staging`, `fin-agent-os-production`
- GitHub Environments: `testing` (Phase 1), `staging` (deferred), `production` (future, with required reviewers)

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

(deploy path, NOT in the request path)
            ┌──────────────────────┐
            │  GitHub Actions      │
            │  (push to main)      │
            └──────┬───────┬───────┘
                   │       │
                   ▼       ▼
              Fly.io    Vercel
              deploy    deploy
                (with deploy-credential secrets only)

(offline / operator path, NOT in the request path, NOT in CI/CD)
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

Rules baked into this topology (already enforced by code/AGENTS.md,
restated here so the deployment plan cannot drift from them):

- **Frontend only talks to FastAPI.** No Supabase client, no LLM SDK,
  no admin token in the browser. (`frontend/AGENTS.md`.)
- **FastAPI is the only thing that talks to Supabase and the LLM.** All
  LLM endpoint / api_key resolution goes through the `model_configs`
  Supabase table via the model-config service boundary; `LLM_*` env
  vars are legacy back-compat only and are NOT in the runtime path.
  (`backend/AGENTS.md`.)
- **`model_configs` is the LLM source of truth** at runtime. The Phase
  1 default is a `zhipu-coding-glm-51` row with `is_default=true`
  pointing at `https://open.bigmodel.cn/api/coding/paas/v4`.
- **Importer is an offline / operator path.** Reads
  `$UPSTREAM_PLUGINS_PATH` from the operator's local filesystem and
  writes to Supabase via the service key. **Not** part of the request
  path, **not** part of the CI/CD path, **not** deployed by Vercel or
  Fly.io.
- **CI/CD never sees runtime secrets.** GitHub Actions only holds
  deploy credentials (`FLY_API_TOKEN`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`,
  `VERCEL_PROJECT_ID_TESTING`). Application runtime secrets
  (`SUPABASE_SERVICE_KEY`, `INTERNAL_ADMIN_TOKEN`, LLM api_keys) live
  in Fly secrets and Supabase rows — never in GitHub Actions.

---

## 4. CI/CD Strategy (Testing — GitHub Actions)

Testing is created and updated **only by GitHub Actions**, never by
ad-hoc `fly deploy` from a developer laptop and never by `vercel
deploy` from a developer laptop. The Vercel CLI runs **inside the
GitHub Actions runner** (installed and invoked by the deploy job), not
on the developer's workstation. This is the forcing function that
keeps testing reproducible and keeps runtime secrets out of developer
machines and out of the CI/CD secret store.

### Control plane & roles (who does what)

- **GitHub Actions** — the sole day-to-day deploy control plane for
  testing. Runs CI, deploys backend to Fly.io, deploys frontend to
  Vercel, runs the post-deploy smoke. Holds **deploy credentials
  only** (`FLY_API_TOKEN`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`,
  `VERCEL_PROJECT_ID_TESTING`).
- **Fly.io dashboard / `flyctl`** — one-time use only. Used to create
  the `fin-agent-os-backend-testing` app, set runtime secrets via
  `fly secrets set` (out-of-band, never via CI), view machine status
  and logs, and perform break-glass recovery. **Not** a routine deploy
  trigger.
- **Vercel dashboard / project settings** — one-time use only. Used
  to create the `fin-agent-os-frontend-testing` project, set the
  repo / root directory link, configure the only public env var
  (`NEXT_PUBLIC_BACKEND_URL`), and view deployment status.
  Operators do **not** need to install or run the Vercel CLI
  locally — routine `vercel deploy` runs inside the GitHub Actions
  runner. The dashboard is **not** a routine deploy trigger.
- **Developer workstation** — local development, local testing, and
  `git push` to `main`. Pushing is what kicks off the CI/CD pipeline;
  the workstation does not deploy directly.
- **Vercel ↔ GitHub Integration / Fly ↔ GitHub Integration** —
  **fallback, not selected.** See ADR
  `docs/architecture/decisions/0001-testing-cicd-control-plane.md`
  for why GitHub Actions to both platforms was chosen over either
  vendor-managed integration. If we ever switch to a vendor
  integration, the ADR's revisit triggers govern the decision.

### Pipeline shape (push to `main`)

```
push to main
  │
  ├── job: backend-ci
  │     - install (uv sync)
  │     - pytest backend/tests/
  │     - ruff check app/ tests/
  │     - openspec validate fin-agent-os --strict
  │
  ├── job: frontend-ci
  │     - npm ci
  │     - npm run lint
  │     - npm run typecheck
  │     - npm run test
  │     - npm run build
  │
  ├── job: deploy-backend-testing   (needs: backend-ci, frontend-ci)
  │     - fly deploy --app fin-agent-os-backend-testing
  │       (using FLY_API_TOKEN; backend runtime secrets are ALREADY
  │       in Fly via `fly secrets set`, not passed by this step)
  │
  ├── job: deploy-frontend-testing  (needs: deploy-backend-testing)
  │     - vercel deploy --prod
  │       (using VERCEL_TOKEN / VERCEL_ORG_ID / VERCEL_PROJECT_ID_TESTING;
  │        NEXT_PUBLIC_BACKEND_URL is configured in the Vercel project,
  │        not passed by this step)
  │
  └── job: testing-smoke            (needs: deploy-frontend-testing)
        - run the §7 testing smoke checklist against the deployed URLs
        - fail the workflow on any §10 stop condition
```

### CI checks (all must pass before any deploy step runs)

**Backend**

- `pytest backend/tests/`
- `ruff check app/ tests/`
- `openspec validate fin-agent-os --strict`

**Frontend**

- `npm run lint`
- `npm run typecheck` (`tsc --noEmit` strict)
- `npm run test` (Vitest)
- `npm run build`

### CD steps

- **Fly deploy** uses `FLY_API_TOKEN` (GitHub Actions secret). The Fly
  app **already has its runtime secrets set** via
  `fly secrets set --app fin-agent-os-backend-testing ...` (operator
  action, out-of-band). The deploy job does not pass, read, or log them.
- **Vercel deploy** uses `VERCEL_TOKEN`, `VERCEL_ORG_ID`,
  `VERCEL_PROJECT_ID_TESTING` (GitHub Actions secrets). The Vercel
  project **already has `NEXT_PUBLIC_BACKEND_URL` set** via the Vercel
  dashboard (operator action). The deploy job does not pass, read, or
  log it.
- **`SUPABASE_SERVICE_KEY` is not in GitHub Actions.** Lives only in Fly
  secrets.
- **`INTERNAL_ADMIN_TOKEN` is not in GitHub Actions.** Lives only in Fly
  secrets.
- **LLM provider api_keys are not in GitHub Actions.** Live only as
  `api_key` values in the `model_configs` Supabase rows the backend
  resolves at runtime.

### Production CI/CD (future, not configured now)

- Same workflow shape (CI jobs + deploy jobs + smoke job).
- Trigger is **not** push to `main`. Options: tag `vX.Y.Z`, dedicated
  `production` branch, or `workflow_dispatch` gated on the `production`
  GitHub Environment.
- The `production` GitHub Environment has **required reviewers**, so a
  deploy needs a human approval before it runs.
- Production secrets are scoped to the `production` environment, never
  visible to the `testing` jobs.

---

## 5. Shared Non-production Data Source Policy

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

- The project is internal MVP. No external customer data, no PII, no
  real customer-bound chat history.
- The non-production data set is small and is intentionally reproducible
  via the importer (`python -m app.importers.import_all`) — losing it is
  inconvenient, not catastrophic.
- Standing up two non-production Supabase projects and keeping their
  `model_configs` / `mcp_servers` in sync by hand would be more failure
  surface than it removes during Phase 1.

This is an **efficiency choice**, not a final architecture. Production
**must** revisit this — see §9.

### Treatment rules (mandatory while shared)

- The shared Supabase project MUST be named explicitly as
  `fin-agent-os-nonprod` (or equivalent) in dashboards, Fly secrets,
  and Vercel env vars. Never label it "shared" or "prod" or leave it
  unnamed.
- No real customer-sensitive data lands in the shared project.
  Synthetic test inputs only.
- Testing smoke (run by the GitHub Actions `testing-smoke` job after
  deploy) is allowed to create rows in `chat_sessions` /
  `chat_messages`. These are non-production artifacts and may be
  truncated.
- `import_all`, `apply` re-runs, `POST /api/model-configs`,
  `PUT /api/model-configs/{id}`, `POST /api/mcp-servers`, and
  `PUT /api/mcp-servers/{id}` against the shared project affect
  **both** development/local and testing simultaneously. Treat them as
  shared-state writes.
- Before any testing smoke (CI or manual), record the current default
  `model_config` (id, provider, model, base_url, masked api_key) so
  that a dev-side change can be detected if smoke fails unexpectedly.

### Risks of the shared model

- A developer running `import_all --apply` locally changes the rows the
  testing environment reads — and the change is reflected on the next
  testing deploy with no separate signal.
- A testing CI smoke run pollutes the dev developer's session list and
  chat history.
- An admin mistake (`PUT /api/model-configs/{id}` with a wrong
  `base_url` or `api_key`) has a wider blast radius — both environments
  break at once.
- We cannot validate the production-data-isolation assumption (RLS-off
  but service-key-only access, importer-only writes, etc.) until we
  actually split the data source. Sharing hides this whole class of
  bug.

### Mitigations

- The shared Supabase project is **explicitly named non-production** so
  no one can confuse it with production later.
- Destructive operations (`TRUNCATE`, `DELETE FROM chat_sessions`,
  schema drops, raw SQL admin actions) require explicit human
  confirmation; never automated, never in CI.
- The default `model_config` snapshot is recorded immediately before
  every testing smoke run, so an unexpected change is caught fast.
- The creation of production (see §9) **must** revisit the data-source
  isolation decision. Sharing across environments is forbidden the
  moment production exists.
- The first real-customer demo or first external-user testing event
  must trigger a re-evaluation of the data-source split, even if
  production has not been built yet. Treat "we are about to show this
  to a real outsider" as a forcing function.

---

## 6. Secret Placement Table

The rule is: **each secret lives in exactly one place, and the place
matches what consumes it.** No copies, no fallbacks.

| Secret | Lives in | Consumed by | Forbidden in |
|---|---|---|---|
| `FLY_API_TOKEN` | GitHub Actions repository secret | Fly deploy step in GitHub Actions | Vercel, Fly runtime, frontend, backend `.env` |
| `VERCEL_TOKEN` | GitHub Actions repository secret | Vercel deploy step in GitHub Actions | Vercel, Fly runtime, frontend, backend `.env` |
| `VERCEL_ORG_ID` | GitHub Actions repository secret | Vercel deploy step in GitHub Actions | Vercel, Fly runtime, frontend, backend `.env` |
| `VERCEL_PROJECT_ID_TESTING` | GitHub Actions repository secret | Vercel deploy step in GitHub Actions | Vercel, Fly runtime, frontend, backend `.env` |
| `SUPABASE_URL` | Fly testing secrets | FastAPI runtime | GitHub Actions, Vercel, browser bundle |
| `SUPABASE_SERVICE_KEY` | Fly testing secrets | FastAPI runtime | **GitHub Actions, Vercel, frontend, browser bundle** |
| `INTERNAL_ADMIN_TOKEN` | Fly testing secrets | FastAPI runtime (`require_admin_token`) | **GitHub Actions, Vercel, frontend, browser bundle** |
| `CORS_ORIGINS` | Fly testing secrets | FastAPI runtime (`CORSMiddleware`) | not a secret, but managed alongside Fly secrets for symmetry |
| `LOG_LEVEL` | Fly testing secrets (or `fly.toml` `[env]`) | FastAPI runtime | n/a |
| `NEXT_PUBLIC_BACKEND_URL` | Vercel testing project env vars | Next.js build + runtime | GitHub Actions (do not pass per-deploy), Fly, backend `.env` |
| LLM provider `api_key` (e.g. GLM-5.1 key) | `model_configs.api_key` row in the (non-production) Supabase project | FastAPI runtime via the model-config service boundary | **GitHub Actions, Vercel, Fly secrets, frontend, browser bundle**, any `LLM_API_KEY` env var |
| `SUPABASE_DB_URL` | operator workstation only | `psql` / `supabase` CLI for schema migrations | GitHub Actions, Vercel, Fly runtime, FastAPI runtime |
| `UPSTREAM_PLUGINS_PATH` | operator workstation only | `python -m app.importers.import_*` | GitHub Actions, Vercel, Fly runtime, FastAPI runtime |

### Hard rules

- **Not allowed in GitHub Actions secrets**: `SUPABASE_SERVICE_KEY`,
  `INTERNAL_ADMIN_TOKEN`, any LLM provider `api_key`. If a workflow
  ever needs them, the workflow is wrong — push the need into the Fly
  runtime or into the `model_configs` row.
- **Not allowed in Vercel env vars (Phase 1)**: `SUPABASE_SERVICE_KEY`,
  `INTERNAL_ADMIN_TOKEN`, any LLM `api_key`, `NEXT_PUBLIC_SUPABASE_URL`,
  `NEXT_PUBLIC_SUPABASE_ANON_KEY`. The frontend has no Supabase client
  in Phase 1; adding these would silently create a second data path the
  rest of the architecture does not account for.
- **Not allowed in frontend code, repo, or browser bundle**: any of the
  above secrets, period. Caught by the §7 smoke checklist and §10 stop
  conditions.

---

## 7. CORS Strategy

- **Testing backend `CORS_ORIGINS`**: must include the Vercel testing
  URL. `http://localhost:3000` may be added only if a local frontend
  needs to call the testing backend during QA; remove it once it is no
  longer needed.
- **Production backend `CORS_ORIGINS`** (future): production frontend
  URL only. No `localhost`. No testing URL.
- **Wildcard `*`**: forbidden in testing and production. Phase 1 has no
  justification on file for `*`; if a future case appears, it must be
  recorded in this document before it is configured.
- **Implementation**: backend reads `CORS_ORIGINS` as a comma-separated
  string in `app/core/config.py` (`Settings.cors_origin_list`) and
  feeds it to `CORSMiddleware.allow_origins` in `app/main.py`. No code
  change needed to switch environments — only the env var value
  differs, and the value lives in Fly secrets, not in GitHub Actions.

---

## 8. Testing Smoke Checklist (run by GitHub Actions after deploy)

The `testing-smoke` job in §4 runs this checklist against the freshly
deployed testing URLs. Failure of any item fails the workflow. The same
checklist is the basis for production smoke (§9), executed against the
production URLs.

Backend (call the testing Fly URL directly):

- [ ] `GET /health` -> 200
- [ ] `GET /api/agents` -> 200, returns 10 agents
- [ ] `GET /api/model-configs` -> 200, contains exactly one row with
  `is_default = true`; that row's `api_key` field is **not** plaintext
  (either omitted, returned as `has_api_key: true`, or masked as
  `****<last4>`)
  - If `GET /api/model-configs/default` is exposed at deploy time, hit
    it as well and confirm the same masking rule applies. (Phase 1 may
    not expose this route; do not fail the smoke if it 404s -- the
    `GET /api/model-configs` assertion above is the source of truth.)

Frontend (open the testing Vercel URL in a real browser, or via a
headless browser step in the workflow):

- [ ] `/agents` loads and lists 10 agents (no client-side error, no
  stale-build fallback -- page is marked `f (Dynamic)` in `next build`
  already)
- [ ] Open `pitch-agent`, send one short Chinese message
- [ ] SSE stream observed in DevTools Network (or recorded by the
  smoke step): event sequence is
  `message_start -> token (1+) -> message_complete -> done`
- [ ] `message_start.message_id` equals `message_complete.message_id`
- [ ] `GET /api/sessions/{id}` (called from the page or hit directly)
  returns the session with both the user message and the assistant
  message persisted
- [ ] Browser console: 0 errors, 0 warnings related to the app
- [ ] Browser JS bundle and Network requests contain **no** secrets --
  no `SUPABASE_SERVICE_KEY`, no `INTERNAL_ADMIN_TOKEN`, no LLM
  `api_key`, no Supabase service URL embedded in client code
- [ ] Fly backend logs for the smoke window contain **no** secrets --
  no plaintext api_key, no service key, no admin token

If any item fails, stop and follow §11.

---

## 9. Production Promotion Gate

Production is **not created by this task**. When we create it, the
following decisions must be made and recorded:

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
  - Generate a fresh `INTERNAL_ADMIN_TOKEN` for production. Never
    reuse the non-production value.
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
- **CI/CD**:
  - Reuse the testing workflow shape (jobs, ordering, smoke).
  - Trigger is **not** push to `main` -- use a tag (`vX.Y.Z`), a
    dedicated `production` branch, or `workflow_dispatch` gated on the
    `production` GitHub Environment.
  - The `production` GitHub Environment has **required reviewers**.
  - Production-scoped deploy secrets live in the `production`
    environment, not in the repository secrets used by testing.
- **Smoke parity**: production smoke checklist is §8, executed against
  the production URLs and the production Supabase project.
- **Non-production cleanup decision**: decide whether to truncate
  non-production `chat_sessions` / `chat_messages` and which rows in
  `model_configs` / `mcp_servers` are kept after the split. Document
  the outcome; do not silently delete.

Production is not "deployed" -- it is **created**, then promoted to
once testing and the above gates pass.

---

## 10. Staging / Pre-production -- Deferred

Staging is **not** created in Phase 1. Reserve the names only (see §2).

Re-evaluate when any of the following becomes true:

- Real external users are about to be onboarded.
- A customer demo requires a stable release-candidate version that
  does not move under the demo's feet.
- Release frequency increases to the point where testing is
  continuously moving and there is no quiet window to validate a
  release candidate.
- Multiple developers ship concurrently and need a shared QA target
  that is not a personal local.
- A risky schema migration is planned (irreversible drops, large
  backfills, breaking column rename) and needs a non-production
  rehearsal on production-shape data.
- Production data is fully separated from non-production and a
  release-candidate validation gate is required before promoting code
  to production.

When activated: stand up `fin-agent-os-backend-staging` (Fly.io,
`nrt`), `fin-agent-os-frontend-staging` (Vercel), and a
`fin-agent-os-staging` Supabase project. Add a `staging` GitHub
Environment between `testing` and `production`. Apply §7 CORS rules
and §8 smoke checklist against the staging URLs.

---

## 11. Deployment Stop Conditions

If **any** of the following occurs during or after a deploy, the
GitHub Actions workflow must fail (or, for items detected after the
fact, the next deploy must be blocked). Do not "fix forward" without
an explicit go-ahead.

- A secret (`SUPABASE_SERVICE_KEY`, `INTERNAL_ADMIN_TOKEN`, any LLM
  `api_key`) appears in: Fly logs, Vercel logs, GitHub Actions logs,
  frontend JS bundle, a browser Network response, or any committed
  file.
- A routine deploy to testing occurred outside GitHub Actions (e.g., a
  developer ran `fly deploy` from a laptop, or ran `vercel deploy`
  locally, without it being a documented one-time bootstrap or
  break-glass action). GitHub Actions is the sole day-to-day control
  plane (§4); any other path is a stop condition.
- A runtime secret is found in GitHub Actions secrets (rule violation
  of §6 -- runtime secrets must live in Fly, not in CI).
- CORS blocks the frontend from calling the backend (browser console
  shows a CORS error, or `Access-Control-Allow-Origin` is missing or
  wrong).
- SSE response is buffered -- the client receives the full response in
  one chunk after the LLM finishes, instead of token-by-token
  streaming. Likely Vercel edge / Fly proxy buffering or wrong
  `Content-Type` / headers.
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
- Testing smoke unexpectedly creates rows in a data source it should
  not be touching (e.g., production Supabase URL accidentally
  configured in testing Fly secrets).

For every stop, capture: the failing check, the request/response or
log excerpt, the env vars in effect (names only, never values), the
GitHub Actions run URL, and the commit hash deployed.

---

## 12. Open Questions for Human Confirmation (CI/CD edition)

Before the testing CI/CD pipeline can be wired up, the operator must
prepare and confirm the following. **Do not paste any secret value
into chat** -- the operator sets each value directly in the relevant
secret store (GitHub repo secrets, Fly secrets, Vercel project env
vars, or Supabase row) and confirms back with a yes/no.

1. **GitHub repo permission**: confirm that the repository allows
   adding GitHub Actions secrets and (later) creating Environments
   with required reviewers.
2. **`FLY_API_TOKEN`**: generated, added to GitHub Actions repository
   secrets (yes/no). Scope: deploy-only if Fly supports it.
3. **Vercel deploy credentials**: `VERCEL_TOKEN`, `VERCEL_ORG_ID`,
   `VERCEL_PROJECT_ID_TESTING` added to GitHub Actions repository
   secrets (yes/no).
4. **Fly app name and org**: confirmed (default suggestion:
   `fin-agent-os-backend-testing`, region `nrt`). Note: existing
   `backend/fly.toml` currently hardcodes `app = "fin-agent-os-backend"`;
   the testing deploy will either need `fly deploy --app <name>`
   override or a per-environment `fly.toml` copy. This is a deploy-time
   decision, not a code change.
5. **Vercel testing project name**: confirmed (default suggestion:
   `fin-agent-os-frontend-testing`).
6. **Shared non-production Supabase decision**: confirm the project URL
   and service-role key to use (the same one local dev uses today, or a
   fresh project) -- and confirmation that it is explicitly named
   non-production in dashboards and Fly secrets.
7. **`INTERNAL_ADMIN_TOKEN` for testing**: reuse the local dev value
   (acceptable for shared non-production), or generate a fresh one.
   Either way, the value is set as a Fly secret, never committed,
   never in GitHub Actions.
8. **Final CORS allowlist** for testing: the Vercel testing URL, plus
   `http://localhost:3000` if local->testing-backend smoke is part of
   the QA loop.
9. **Acceptance of the shared-data-source risks in §5** as the Phase 1
   working assumption until production is created.
10. **Acceptance of GitHub Actions as the sole day-to-day deploy
    control plane** for testing (per §4 and ADR 0001), with Vercel /
    Fly dashboards reserved for one-time bootstrap and break-glass
    only.

A separate, operator-facing checklist with the concrete preparation
steps lives at
`docs/deployment/human-preparation-checklist.md`.

No deploy action and no GitHub Actions workflow file is created until
items 1-10 are answered.
