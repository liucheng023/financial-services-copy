# Human Preparation Checklist — Testing CI/CD Bootstrap

**Audience**: the operator who will set up the first testing deploy.
**Goal**: have everything ready so that the first GitHub Actions run
of the testing pipeline (when we eventually write the workflow) can
succeed.
**Scope**: testing environment only. Production has its own future
checklist.
**Source-of-truth references**:
`docs/deployment/environment-readiness-plan.md` and
`docs/architecture/decisions/0001-testing-cicd-control-plane.md`.

## Hard rule before you start

> **Never paste any secret value into chat. Never commit any secret
> value to the repo. Set each value directly in the platform that
> owns it (GitHub repo secrets, Fly secrets, Vercel project env,
> Supabase row), then confirm back with a yes/no.**
>
> Forbidden in chat / repo: `FLY_API_TOKEN`, `VERCEL_TOKEN`,
> `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID_TESTING`,
> `SUPABASE_SERVICE_KEY`, `INTERNAL_ADMIN_TOKEN`, any LLM provider
> `api_key`, the Supabase service URL with its key, and
> `SUPABASE_DB_URL`.

## 1. GitHub repo secrets (deploy credentials only)

These four go into **Settings -> Secrets and variables -> Actions ->
Repository secrets**. They are *deploy credentials*, not application
runtime secrets.

- [ ] `FLY_API_TOKEN` -- generated in Fly dashboard or via
  `fly tokens create deploy --app fin-agent-os-backend-testing`.
  Scope: deploy-only on the testing Fly app if Fly supports it.
- [ ] `VERCEL_TOKEN` -- generated in Vercel dashboard
  (Account -> Settings -> Tokens). Scope: smallest viable.
- [ ] `VERCEL_ORG_ID` -- copied from Vercel project settings.
- [ ] `VERCEL_PROJECT_ID_TESTING` -- copied from the testing Vercel
  project settings (created in step 3 below).

What MUST NOT be in GitHub Actions secrets:

- [ ] `SUPABASE_SERVICE_KEY` -- belongs in Fly secrets.
- [ ] `INTERNAL_ADMIN_TOKEN` -- belongs in Fly secrets.
- [ ] Any LLM provider `api_key` -- belongs in the
  `model_configs.api_key` row in Supabase.

If you find any of these in GitHub Actions, that is a §11 stop
condition in the environment-readiness-plan.

## 2. Fly.io testing app (backend)

Done **once** by the operator via Fly dashboard / `flyctl`, before
the first CI/CD run.

- [ ] Create the Fly app `fin-agent-os-backend-testing` in your Fly
  organization. Region: `nrt` (Tokyo).
- [ ] Decide how to handle the existing `backend/fly.toml` which
  currently hardcodes `app = "fin-agent-os-backend"`. Two options:
  - (a) deploy via `fly deploy --app fin-agent-os-backend-testing`
    (override at deploy time), or
  - (b) maintain a per-environment `fly.toml` copy.
  Either is acceptable; it is a deploy-time decision, not a code
  change.
- [ ] Set runtime secrets via `fly secrets set --app
  fin-agent-os-backend-testing` (out-of-band, never via CI):
  - [ ] `SUPABASE_URL`
  - [ ] `SUPABASE_SERVICE_KEY`
  - [ ] `INTERNAL_ADMIN_TOKEN` (decide reuse-vs-rotate; see §4 in
    `environment-readiness-plan.md` and item 5 below)
  - [ ] `CORS_ORIGINS` (final allowlist; see step 5 below)
  - [ ] `LOG_LEVEL` -- optional; defaults to `INFO` from `fly.toml`
    `[env]`.
- [ ] Confirm `GET /health` works manually once after the first
  bootstrap deploy (which may be a one-time manual `fly deploy` from
  the operator workstation to seed the app). After that, all
  deploys must go through GitHub Actions.

The Fly dashboard / `flyctl` is **not** a routine deploy trigger
after bootstrap. Routine deploys come from GitHub Actions only.

## 3. Vercel testing project (frontend)

Done **once** by the operator via the **Vercel dashboard / project
settings** (web UI), before the first CI/CD run. The operator does
**not** need to install or run the Vercel CLI on their workstation --
the CLI is installed and invoked inside the GitHub Actions runner by
the deploy job.

- [ ] Create the Vercel project named
  `fin-agent-os-frontend-testing` (or your chosen equivalent).
- [ ] Link the project to the GitHub repo, set the **root directory**
  to `2033_fin_agent/frontend/` (this is a monorepo), but **do NOT
  enable Vercel's GitHub Integration auto-deploy on `main`**.
  Routine deploys come from GitHub Actions only; auto-deploy would
  race the workflow and bypass the unified release gate (ADR 0001).
- [ ] In Vercel project Settings -> Environment Variables, set:
  - [ ] `NEXT_PUBLIC_BACKEND_URL` -- the testing Fly backend URL
    (e.g., `https://fin-agent-os-backend-testing.fly.dev`). This
    is the **only** env var the Vercel testing project gets in
    Phase 1.
- [ ] Confirm the project's `VERCEL_ORG_ID` and
  `VERCEL_PROJECT_ID` values from the dashboard (Project Settings ->
  General), and store them as `VERCEL_ORG_ID` and
  `VERCEL_PROJECT_ID_TESTING` in GitHub Actions secrets (see
  step 1).
- [ ] Use the Vercel dashboard to view deployment status after each
  GitHub Actions run. The dashboard is **not** a routine deploy
  trigger; it is for visibility and break-glass only.

What MUST NOT be in Vercel env vars (Phase 1):

- [ ] `SUPABASE_SERVICE_KEY`
- [ ] `INTERNAL_ADMIN_TOKEN`
- [ ] Any LLM provider `api_key`
- [ ] `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`
  (frontend has no Supabase client in Phase 1)

## 4. Supabase shared non-production project

`development/local` and `testing` may share the same non-production
Supabase project initially (see §5 in `environment-readiness-plan.md`).
Confirm the following:

- [ ] The Supabase project URL and service-role key you intend to use
  for testing -- either the same project local dev uses today, or a
  fresh one. **Do not paste the values in chat.**
- [ ] The project is explicitly named **non-production** in the
  Supabase dashboard label, in Fly secret names where helpful (e.g.,
  comments alongside `SUPABASE_URL`), and in any internal doc you
  share with operators. Forbidden labels: `shared`, `prod`,
  unnamed.
- [ ] Schema migrations have been applied (`SUPABASE_DB_URL` is used
  only on operator workstation; CI never sees it).
- [ ] The default `model_configs` row exists: exactly one row with
  `is_default = true`, `base_url`
  `https://open.bigmodel.cn/api/coding/paas/v4`, a working
  `api_key`, and a valid model id. The `api_key` value is set
  **inside Supabase**, never via env vars and never via CI.
- [ ] Importer has been run at least once
  (`python -m app.importers.import_all --apply` from operator
  workstation with `UPSTREAM_PLUGINS_PATH` set) so that `agents`,
  `verticals`, `skills`, `mcp_servers` are populated. Confirm
  `GET /api/agents` will return 10 once the backend is deployed.
- [ ] You accept the §5 shared-data-source risks as the Phase 1
  working assumption until production is created.

## 5. Decisions you must make explicitly

- [ ] **`INTERNAL_ADMIN_TOKEN` for testing**: reuse the local dev
  value (acceptable for shared non-production) **or** generate a
  fresh one. Either way, the value is set as a Fly secret -- never
  committed, never in GitHub Actions, never in Vercel.
- [ ] **Final CORS allowlist for testing**: the Vercel testing URL
  is required. Add `http://localhost:3000` only if local frontend
  needs to call the testing backend during QA; remove later.
  Wildcard `*` is forbidden without written justification.
- [ ] **`GET /api/model-configs/default` exposure**: confirm whether
  the deployed backend exposes this route, so the smoke checklist
  can target it. If absent, the smoke falls back to
  `GET /api/model-configs` and the masking assertion still applies.

## 6. Final go/no-go before writing the workflow

When the items above are all checked, confirm back with:

- [ ] All §1, §2, §3, §4, §5 items above are done.
- [ ] You accept GitHub Actions as the sole day-to-day deploy
  control plane for testing (per ADR 0001 and §4 of
  `environment-readiness-plan.md`).
- [ ] No secret value has been pasted into chat or committed to the
  repo at any point during this checklist.

When that confirmation arrives, the next task is to write the
GitHub Actions workflow file -- and only then.
