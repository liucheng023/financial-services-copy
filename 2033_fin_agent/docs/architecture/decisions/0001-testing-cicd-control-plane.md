# ADR 0001 — Testing CI/CD Control Plane

- **Status**: Accepted
- **Date**: 2026-06-11
- **Deciders**: FinAgentOS Phase 1 team
- **Scope**: Phase 1 *testing* environment. Production CI/CD inherits
  the same shape but adds a protected GitHub Environment with required
  reviewers; that scope is out of this ADR.

## Context

FinAgentOS Phase 1 is moving from `development/local` (validated
end-to-end against real Supabase + real GLM-5.1, captured in
`docs/handoffs/phase-1-current-acceptance.md`) to a deployed `testing`
environment. The product is not a one-off demo -- it is on the
trajectory to a production B2B service. Phase 1 has already locked in:

- Frontend = Next.js on Vercel.
- Backend = FastAPI on Fly.io (region `nrt`).
- Runtime LLM source of truth = the `model_configs` Supabase table
  (not env vars). LLM provider api_keys live in that table, never in
  CI.
- Backend runtime secrets (`SUPABASE_SERVICE_KEY`,
  `INTERNAL_ADMIN_TOKEN`) live in Fly secrets, never in CI.
- Frontend exposes only `NEXT_PUBLIC_BACKEND_URL`. No Supabase
  client, no admin token, no LLM api_key in the browser.
- Strict CI/CD is a hard requirement (operator decision): testing
  must not be deployed by ad-hoc laptop commands.

The remaining question is *which system orchestrates the testing
deploys*. Three plausible options were considered.

## Decision

**Use GitHub Actions as the single control plane for testing CI/CD.**
GitHub Actions runs all CI (backend and frontend), then deploys the
backend to Fly.io via `flyctl` and the frontend to Vercel via the
Vercel CLI -- both installed and invoked inside the GitHub Actions
runner, never on a developer workstation. It then runs the
post-deploy smoke checklist
(`docs/deployment/environment-readiness-plan.md` §8) as a workflow
job.

Vercel <-> GitHub Integration and Fly <-> GitHub Integration are
**fallback options, not selected**. The Vercel and Fly dashboards are
reserved for one-time bootstrap (creating the app/project, setting
runtime secrets via `fly secrets set`, configuring
`NEXT_PUBLIC_BACKEND_URL` in the Vercel project), break-glass
recovery, and status viewing -- they are **not** a routine deploy
trigger.

## Alternatives Considered

### Option A -- Vercel Integration + Fly Integration (vendor-managed each side)

Vercel's native GitHub Integration auto-deploys the frontend on every
push to `main`. Fly's GitHub integration / `fly deploy` GitHub Action
auto-deploys the backend on every push to `main`. CI runs separately
or not at all.

- **Pros**: zero CI/CD code to write. Each platform owns its piece.
  Cheapest to set up.
- **Cons**:
  - Two control planes. Frontend and backend can finish deploying at
    different times, with no single gate that says "both are live
    and smoke-tested."
  - No place to run a unified post-deploy smoke that exercises the
    *whole* stack (frontend + backend + Supabase + LLM) as a single
    workflow result.
  - Hard to evolve into production with a manual approval gate that
    covers both sides at once.
  - CI gates (pytest, ruff, openspec, lint, typecheck, tests, build)
    are not naturally co-located with the deploy step; easy for a
    bad commit to deploy because each platform only runs its own
    sanity check.
  - Status reporting is split across the GitHub PR UI, Vercel
    dashboard, and Fly dashboard.
- **Verdict**: rejected. Splits the control plane and makes a
  unified release gate hard.

### Option B -- Vercel Integration + GitHub Actions to Fly

Frontend is auto-deployed by Vercel's GitHub Integration. Backend is
deployed by a GitHub Actions workflow using `flyctl`. CI lives in
GitHub Actions.

- **Pros**: one less piece of CI/CD code than Option C. Vercel
  preview deploys come "for free" on every PR.
- **Cons**:
  - Still two control planes for production-bound deploys: the
    `main` push goes through *both* Vercel's integration and the
    GitHub Actions workflow simultaneously. Ordering is not
    guaranteed (frontend can land before backend, or vice versa).
  - No single workflow result that says "the whole stack is healthy
    post-deploy."
  - Mismatch between testing and production: when production needs
    a protected GitHub Environment with required reviewers,
    Vercel's auto-deploy bypasses that gate for the frontend.
  - Smoke can run against a frontend that has already deployed
    before the backend the smoke needs is up.
- **Verdict**: rejected. The unified gate and ordering problems
  outweigh the convenience of Vercel previews.

### Option C -- GitHub Actions to both Fly and Vercel  *(selected)*

GitHub Actions runs CI for both sides, then explicitly invokes
`flyctl deploy` and `vercel deploy --prod` from inside the GitHub
Actions runner (CLIs installed by the workflow, not on a developer
workstation) in jobs whose ordering is controlled by the workflow,
then runs a smoke job that depends on both deploys completing.

- **Pros**:
  - **Single control plane.** One place to look at status, one
    workflow result.
  - **Frontend and backend share the same commit and the same
    workflow gate.** A PR either ships both halves or ships
    neither.
  - **Unified post-deploy smoke** can act as the release gate --
    the workflow fails if any §8 check fails, blocking subsequent
    deploys.
  - **Production-future ready.** Production CI/CD reuses the same
    workflow shape behind a protected GitHub Environment with
    required reviewers; no architectural change needed to add the
    approval step.
  - **Less platform-state confusion.** Vercel/Fly dashboards become
    operator tools (one-time setup, secrets, status viewing,
    break-glass), not deploy triggers.
- **Cons**:
  - **More workflow code to write and maintain** vs Option A.
  - **Vercel deploy token / org id / project id must be configured**
    as GitHub Actions secrets.
  - **Initial bootstrap is still manual**: someone has to create
    the Fly app, create the Vercel project, set the Fly runtime
    secrets, and set `NEXT_PUBLIC_BACKEND_URL` in the Vercel
    project before the first CI/CD run can succeed.
  - We give up Vercel's automatic preview deploys on PRs
    (mitigable by adding a separate PR-preview workflow later if
    needed).
- **Verdict**: selected.

## Why C was selected over A and B

- **Single control plane.** Deploy status, deploy failure, deploy
  history, and post-deploy smoke all live in one GitHub Actions run.
  This dramatically reduces "what is currently deployed and is it
  healthy?" ambiguity.
- **Same commit, same gate, both sides.** Frontend and backend are
  always deployed from the same commit, behind the same CI gate, in
  a defined order (backend first so the frontend's
  `NEXT_PUBLIC_BACKEND_URL` is reachable when smoke starts).
- **Unified smoke as the release gate.** The §8 testing smoke runs
  as a workflow job that depends on both deploys. A bad combination
  of frontend + backend fails the workflow and is visible at the PR
  / commit level.
- **Production reuses the shape.** When we build production CI/CD,
  the same workflow shape is wrapped behind a protected GitHub
  Environment with required reviewers. No second integration story
  to invent.
- **Less platform-state confusion.** Operators interact with Vercel
  and Fly dashboards only when they have to (creating apps, setting
  secrets, break-glass). Routine deploys leave a single audit trail
  in GitHub Actions.

## Costs and Trade-offs (accepted)

- Vercel deploy tokens (`VERCEL_TOKEN`, `VERCEL_ORG_ID`,
  `VERCEL_PROJECT_ID_TESTING`) must be configured as GitHub Actions
  secrets. The operator generates them in the Vercel dashboard
  out-of-band; they never appear in chat or in the repo.
- The workflow is more complex than enabling vendor integrations.
  Mitigated by keeping the workflow small and explicit, and by
  treating it as the single artifact that captures release policy.
- One-time bootstrap (Fly app creation, Vercel project creation,
  Fly runtime secrets, Vercel `NEXT_PUBLIC_BACKEND_URL`) is still a
  human action. That is intentional -- the bootstrap policy is
  human-decided, the routine deploy is machine-executed.
- We lose Vercel's automatic PR preview deploys. If preview deploys
  become useful later, we add a separate workflow that does
  `vercel deploy` (no `--prod`) on PR events; that workflow does
  not affect testing.

## Current Conditions That Justify Option C Now

- The project is not a one-off demo -- it has a documented path
  toward production.
- The operator explicitly requires strict CI/CD with a unified
  release gate.
- The repo is a monorepo with `2033_fin_agent/backend/` and
  `2033_fin_agent/frontend/` side by side; a single workflow can
  cleanly own both pipelines.
- Testing and `development/local` may temporarily share a
  non-production Supabase project, so the cost of "wrong half of
  the stack deployed" is real: a half-deployed change can corrupt
  the shared `model_configs` / `chat_messages` data for both
  environments.
- Production-future planning already calls for a protected GitHub
  Environment with required reviewers, which is a GitHub Actions
  concept; standardizing on it now avoids a later migration.

## Revisit Triggers

This ADR should be revisited if any of the following becomes true:

- `vercel deploy` (CLI) executed inside the GitHub Actions runner
  proves unreliable (consistent flakiness, broken `--prod` semantics,
  deploy failures that the Vercel Integration would have handled).
- Vercel or Fly ship official GitHub-integration features that
  natively support: a unified post-deploy smoke gate, required-
  reviewer approval, and explicit cross-platform deploy ordering.
- We add staging or split the frontend / backend into multiple
  deployable targets (e.g., a second backend, an admin frontend),
  and the workflow becomes harder to maintain than two vendor
  integrations would be.
- Production rollout shows we need per-platform incident isolation
  that GitHub Actions cannot provide (e.g., we want to roll back
  the backend without re-running the frontend deploy).

## Consequences

- `docs/deployment/environment-readiness-plan.md` §1, §2, §4 are
  written to this decision.
- The forthcoming GitHub Actions workflow file will be one workflow
  per environment (testing now, production later behind a protected
  GitHub Environment), with jobs in the order: backend CI, frontend
  CI, deploy backend (Fly), deploy frontend (Vercel), testing
  smoke.
- Operators MUST NOT enable Vercel <-> GitHub Integration auto-
  deploy on `main` for the testing project, because it would race
  the GitHub Actions workflow and bypass the unified release gate.
  If Vercel preview deploys are desired for PRs, they are added
  via a separate workflow, not via the vendor integration.
- The deploy credentials in GitHub Actions secrets are
  `FLY_API_TOKEN`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`,
  `VERCEL_PROJECT_ID_TESTING` -- and no others. Application
  runtime secrets do not enter GitHub Actions, ever.

## References

- `docs/deployment/environment-readiness-plan.md` -- the
  environment matrix, CI/CD pipeline shape, secret placement table,
  CORS strategy, smoke checklist, and stop conditions this ADR
  governs.
- `docs/deployment/human-preparation-checklist.md` -- the
  operator-facing preparation checklist that captures what must be
  set up by hand before the first CI/CD run.
- `2033_fin_agent/AGENTS.md`, `backend/AGENTS.md`,
  `frontend/AGENTS.md` -- the source-of-truth rules this ADR is
  consistent with.
