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

### Task 1: Supabase Schema Contract ✅

- [x] Write SQL migration `2033_fin_agent/supabase/migrations/0001_initial_schema.sql` covering all tables: `agents`, `skills`, `verticals`, `mcp_servers`, `agent_skills`, `agent_mcps`, `vertical_skills`, `vertical_mcps`, `chat_sessions`, `chat_messages`, `model_configs`
- [x] `chat_sessions.user_id` MUST be `UUID NULL` (Phase 2 migration readiness)
- [x] `model_configs.api_key` and `mcp_servers.api_key` stored as plain `TEXT` (NOT `_encrypted` — see backend/AGENTS.md "Secret Storage Policy"). `mcp_servers.api_key` is nullable.
- [x] Include unique constraints on `slug` columns and on association-table composite keys
- [x] Include indexes: `agents(slug)`, `skills(slug)`, `verticals(slug)`, `mcp_servers(slug)`, `chat_sessions(agent_id)`, `chat_messages(session_id, created_at)`
- [x] `chat_messages` covers: `role`, `content`, `tool_calls` (jsonb), `tool_results` (jsonb), `created_at`
- [x] Add SQL comments at the top of `mcp_servers` and `model_configs` documenting the secret-disclosure policy (responses never return plaintext `api_key`)
- [x] Statically validate the SQL: pipe through `psql --no-psqlrc -f - --set ON_ERROR_STOP=1` against a throwaway local Postgres (e.g., `docker run --rm -d postgres:16`) — this proves the SQL parses and executes, without committing to a real Supabase project.
- [ ] If a real Supabase project + service-role credentials are available, apply the migration there and record the result; otherwise SKIP this step and explicitly note "no Supabase environment available yet". → **SKIPPED**: no Supabase environment available yet.
- **Deliverable**: `2033_fin_agent/supabase/migrations/0001_initial_schema.sql` committed; SQL passes syntactic + structural validation on a throwaway Postgres
- **Verification**: Container run logs show all `CREATE TABLE` / `CREATE INDEX` succeed with exit code 0; `\dt` lists all 11 tables; `\d+ chat_sessions` shows `user_id` as nullable UUID

### Task 2: Importer — Agent Parser

Split into two gates so we can ship the parser independently of any Supabase environment. The agent-skills / agent-mcps association tables are populated in Task 3 alongside the skill and MCP importers — Task 2 only touches the `agents` table.

#### Task 2a — Parse-only (no Supabase required) ✅

- [x] Add minimal backend Python scaffold needed by the importer: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/importers/__init__.py`, `backend/tests/`
- [x] `backend/app/importers/agent_parser.py`: pure parser. Reads one agent markdown + its sibling `plugin.json`, returns a `ParsedAgent` dataclass with `slug`, `name`, `description`, `system_prompt`, `workflow`, `guardrails`, `outputs`, `raw_frontmatter`, `plugin_metadata`, `source_path`. NO Supabase, NO FastAPI, NO I/O beyond reading the two given files.
- [x] `backend/app/importers/import_agents.py`: CLI that resolves `UPSTREAM_PLUGINS_PATH`, discovers `agent-plugins/*/agents/*.md`, parses each, and emits a JSON summary to stdout. Default mode is `--dry-run`. `--apply` is reserved for Task 2b and currently exits non-zero with a clear "not implemented in Task 2a" message.
- [x] Read-only invariant: parser MUST NOT open any upstream file for writing. Enforced by unit test that compares mtime + mode before/after parsing real upstream files.
- [x] Missing `UPSTREAM_PLUGINS_PATH` raises `MissingUpstreamPathError` from the resolver and exits the CLI with status 2 and a clear message naming the env var.
- [x] Unit tests cover: real `pitch-agent` parse, 10-agent discovery, read-only filesystem invariant, missing-env error, dry-run CLI summary contains `pitch-agent`, frontmatter validation rejects missing/blank `name`.
- **Deliverable**: `python -m app.importers.import_agents` (dry-run) prints a JSON summary listing all 10 upstream agents with non-empty system prompts. No Supabase touched.
- **Verification**: `pytest backend/tests/importers/test_agent_parser.py -v` → 9/9 pass; CLI dry-run output shows `"discovered": 10, "parsed": 10, "errors": 0` and every agent has `has_workflow / has_guardrails / has_outputs = true`.

#### Task 2b — Supabase write gate ✅

- [x] Wire `--apply` to `app.importers.supabase_writer.upsert_agents` that upserts each `ParsedAgent` into the `agents` table on `slug` conflict (idempotent re-run).
- [x] Requires `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`; CLI fails fast with status 2 if either is missing.
- [x] Live `--apply` ran against the real Supabase project and `SELECT count(*) FROM agents` returns `10`.
- **Deliverable**: `python -m app.importers.import_agents --apply` against the real Supabase project results in `SELECT count(*) FROM agents = 10`.
- **Verification**: Live `psql` against the configured Supabase reports `agents = 10`. Writer covered by `tests/importers/test_supabase_writer.py` (10 mocked-client tests asserting conflict keys, FK lookup, idempotent payload, `api_key` never invented).

### Task 3: Importer — Skill + Vertical + MCP Parsers

Split into two gates so we can ship the parsers + association dry-run independently of any Supabase environment.

#### Task 3a — Parse-only + association dry-run (no Supabase required) ✅

- [x] `backend/app/importers/_cli_common.py`: shared `UPSTREAM_PLUGINS_PATH` resolver + Supabase env-availability check (used by every importer CLI so they all fail the same way with the same message)
- [x] `backend/app/importers/vertical_parser.py`: `parse_vertical_plugin(plugin_json, slug)` returns `ParsedVertical(slug, name, description, raw_manifest, source_path)`
- [x] `backend/app/importers/skill_parser.py`: `parse_skill_file(SKILL.md, vertical_slug)` returns `ParsedSkill(slug, name, description, content, vertical_slug, raw_frontmatter, source_path)`; preserves the full SKILL body in `content`
- [x] `backend/app/importers/mcp_parser.py`: `collect_all_mcp_servers(root)` merges every `vertical-plugins/*/.mcp.json`; surfaces the documented `capiq → sp-global` alias inside `tool_name_map`
- [x] `backend/app/importers/associations.py`: dry-run derivation of `vertical_skills`, `vertical_mcps`, and `agent_mcp_candidates` with `matched / aliased / unmatched` resolution buckets
- [x] CLIs: `import_verticals.py`, `import_skills.py`, `import_mcps.py`, `import_all.py`. All default to `--dry-run`; `--apply` is reserved and exits 2 with a "not implemented in Task 3a" message
- [x] All parsers read-only relative to upstream (enforced by mtime + mode unit test against real upstream files of all three kinds + by docker `:ro` mount during test execution)
- [x] Missing `UPSTREAM_PLUGINS_PATH` exits each CLI with status 2 and a message naming the env var
- [x] Upstream-reality findings encoded in tests: 7 verticals, 55 SKILL.md files, 11 MCP slugs centralized in `financial-analysis/.mcp.json` (other verticals' `.mcp.json` exist but with empty `mcpServers`); only `capiq` is a documented user-facing alias mapping to `sp-global` (S&P Global Kensho Capital IQ)
- **Deliverable**: `python -m app.importers.import_all` (dry-run) prints a JSON report containing exactly `agents: 10, verticals: 7, skills: 55, mcps: 11, vertical_skills: 55, vertical_mcps: 11, agent_mcp_candidates: 15` (matched 4, aliased 4, unmatched 7) with `supabase_write: false`.
- **Verification**: `pytest backend/tests/importers/ -v` → 23/23 pass (9 from Task 2a + 14 new); `python -m app.importers.import_all` smoke-run exits 0 with the counts above.

#### Task 3b — Supabase write gate ✅

- [x] `backend/app/importers/supabase_writer.py`: sync `supabase-py` client + per-table upsert helpers. Entity tables use `on_conflict="slug"`; association tables use composite `on_conflict="<fk1>,<fk2>"`. `mcp_servers` writer omits `api_key` from the row dict (writes NULL, never invents a placeholder value).
- [x] `--apply` on each of `import_verticals.py`, `import_skills.py`, `import_mcps.py`, `import_agents.py`, `import_all.py` calls the writer. `import_all.py` orchestrates the dependency order: verticals → mcp_servers → agents → skills → vertical_skills → vertical_mcps → agent_mcps.
- [x] Requires `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`; fail fast with status 2 if either is missing. Writer exception → exit 3.
- [x] Idempotent: second `--apply` against the live Supabase produced identical `written.*` counts and no row-count delta in psql.
- [x] `agent_mcps` only writes `matched + aliased` candidates (4 + 4 = 8 rows); 7 `unmatched` aliases are reported in `agent_mcp_candidates` and counted in `written.agent_mcps_skipped_unmatched`, never persisted.
- [x] `--apply` actually ran against the real Supabase project and post-run `psql` counts match the deliverable below exactly.
- **Deliverable**: After `--apply` on the real Supabase, `psql` reports `verticals=7, skills=55, mcp_servers=11, vertical_skills=55, vertical_mcps=11, agent_mcps=8` and `count(*) FROM mcp_servers WHERE api_key IS NOT NULL = 0`.
- **Verification**: Live `psql` against the configured Supabase reports the expected counts. Wire-level idempotency covered by `tests/importers/test_supabase_writer.py::test_idempotent_second_call_produces_same_payload`; row-level idempotency verified by running `--apply` twice in sequence with identical post-counts. `pytest backend/tests/` → 49/49 pass (39 from Tasks 2a + 3a + 4 + 10 new writer tests).

### Task 4: Backend Scaffold ✅

> **Superseded note (historical context):** The original Task 4 config contract listed `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` and `UPSTREAM_PLUGINS_PATH` as part of `Settings`. This has been superseded by two follow-up cleanups documented below: (1) Task 8 made `LLM_*` **legacy optional** because the runtime LLM source of truth moved to the Supabase `model_configs` table read through `model_config_service`; (2) Task 4 follow-up "Config contract cleanup v2" removed `UPSTREAM_PLUGINS_PATH` from `Settings` entirely — it is now **importer-only** (read by `app/importers/_cli_common.py` via `os.environ`, never by FastAPI). The historical bullet below is preserved for change-log fidelity; consult `app/core/config.py` and `backend/AGENTS.md` "Configuration" for the current runtime contract.

Scope intentionally narrow: runtime spine + secret-safe config + Supabase boundary + admin guard + Supabase smoke. The read-only `/api/agents` family stays in Task 5 so this gate is fully testable without Supabase credentials.

- [x] `backend/pyproject.toml`: adds `fastapi`, `uvicorn[standard]`, `pydantic>=2.7`, `pydantic-settings`, `supabase>=2.7`, `httpx`; dev adds `pyright` to match `backend/AGENTS.md`
- [x] `backend/app/main.py`: FastAPI app, CORS from `CORS_ORIGINS`, registers `/health` only. No `/api/*` yet (asserted by `test_openapi_lists_only_health_in_phase4`)
- [x] `backend/app/core/config.py`: Pydantic `BaseSettings` for `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `UPSTREAM_PLUGINS_PATH`, `INTERNAL_ADMIN_TOKEN`, `CORS_ORIGINS`, `LOG_LEVEL`. All credential fields use `pydantic.SecretStr` so plaintext cannot appear in `repr`, `str`, or `ValidationError` messages (asserted by 2 dedicated tests). Required fields fail validation with the env name when missing.
- [x] `backend/app/core/supabase.py`: single `get_supabase()` async factory built on `supabase>=2`'s `acreate_client`. All Supabase access must go through this boundary; business code is forbidden from constructing its own client (rule documented in module docstring)
- [x] `backend/app/core/deps.py`: `require_admin_token` FastAPI dependency. Uses `hmac.compare_digest`. On failure raises a 401 whose body follows the RFC 7807 problem shape declared in backend/AGENTS.md (`code=admin_token_invalid`)
- [x] `backend/app/api/health.py`: `GET /health` returns `{"status":"ok","service":"fin-agent-os-backend"}`. Intentionally does NOT touch Supabase or the LLM so an outage cannot mark the service unhealthy
- [x] `backend/scripts/smoke_supabase.py`: standalone read-only connectivity check. Probes all 11 Phase 1 tables with `count="exact", head=True`. Exit codes — 0 ok, 2 missing `SUPABASE_URL` / `SUPABASE_SERVICE_KEY`, 3 a probed table errored. Never writes
- [x] `backend/Dockerfile`: `python:3.11-slim` base, installs from `pyproject.toml`, runs `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- [x] `backend/fly.toml`: `primary_region = "nrt"`, http health check on `/health`, scale-to-zero defaults
- [x] `backend/.env.example`: every required + optional env var with empty values; `.env` already in `.gitignore`
- **Deliverable**: `uvicorn app.main:app` starts; `GET /health` returns 200 with the documented JSON; `python -m scripts.smoke_supabase` exits 2 with a clear message when Supabase env is missing.
- **Verification**: `pytest backend/tests/ -v` → 37/37 pass (23 from Tasks 2a+3a + 14 new in `tests/runtime/`); `ruff check .` → clean. `pyright` is wired into `pyproject.toml` but was not executed in the current sandbox because the bundled node download exceeds the available network budget — CI must run it.
- **Supabase connection status**: NOT attempted. The smoke script and the rest of the scaffold have not been pointed at a real Supabase project. No data was read or written.

## Batch 2: Backend Core

> **Execution order note (2026-06):** Task 8 (Model Config API) is executed **before** Task 7 (Chat Session + Streaming Engine). The chat runtime in Task 7 needs a stable `default` model config and a tested LLM connection-test boundary; building Task 8 first lets Task 7 read the configured LLM through a known surface instead of reading env vars directly. Numbering is preserved for spec stability; only the implementation order changes.

### Task 5: Read-only APIs (Agents, Verticals, MCPs) ✅

- [x] `GET /api/agents` (list with skill_count, mcp_count)
- [x] `GET /api/agents/{slug}` (detail with skills list, mcps list, workflow, guardrails)
- [x] `GET /api/verticals` (list)
- [x] `GET /api/verticals/{slug}` (detail with skills, mcps)
- [x] `GET /api/mcp-servers` (list with has_api_key, no plaintext api_key)
- [x] `GET /api/mcp-servers/{id}` (detail with masked_api_key, tool_name_map, no plaintext)
- [x] `POST /api/mcp-servers` (admin-protected, create new MCP config)
- [x] `PUT /api/mcp-servers/{id}` (admin-protected)
- [x] `X-Admin-Token` validation on POST/PUT via `Depends(require_admin_token)`
- [x] Layered architecture: api/ (thin handlers) → services/ (business logic) → supabase client
- [x] Pydantic request/response schemas in models/schemas.py
- [x] RFC 7807 problem-detail errors: agent_not_found, vertical_not_found, mcp_server_not_found
- [x] Secret policy: api_key never returned in plaintext; list returns has_api_key; detail returns masked_api_key
- [x] `get_supabase` usable as `Depends()` for test injectability
- [x] 13 API tests with FakeAsyncClient covering all endpoints, auth, not_found, secret masking
- **Deliverable**: All CRUD endpoints return correct data from Supabase
- **Verification**: 63/63 pytest pass; ruff clean; mocked Supabase client; api_key never in response text

### Task 6: MCP Adapter Layer ✅

- [x] Integrate `mcp-use` library (`pip install mcp-use`)
- [x] `app/adapters/mcp_adapter.py`:
  - Load MCP server configs from Supabase for a given agent
  - Initialize MCPClient connections
  - Use OpenAIMCPAdapter to convert tools → OpenAI function schema
  - Implement tool_executors: model returns tool_calls → execute via adapter → return results
- [x] `app/services/mcp_service.py`: business logic wrapping the adapter
- [x] Lazy initialization per chat session (different agents have different MCP access)
- [x] Graceful degradation: if an MCP server is unreachable, log warning, skip its tools
- **Deliverable**: Given an agent slug, MCP adapter returns a list of OpenAI function definitions + can execute tool calls
- **Verification**: 8 mocked adapter/service tests cover mcp-use config construction, OpenAI function schema exposure, tool execution, unknown tool handling, exception redaction, graceful initialization degradation, Supabase agent→MCP config loading, and service wrapper delegation. `pytest backend/tests/` → 71/71 pass; `ruff check` clean; `openspec validate fin-agent-os --strict` pass. `pyright` attempted in Docker but timed out installing bundled prebuilt node, same sandbox limitation as prior tasks.

### Task 8: Model Config API ✅

- [x] `GET /api/model-configs` (list with `has_api_key`, never plaintext)
- [x] `GET /api/model-configs/default` (returns the active config; 404 with RFC 7807 `model_config_not_found` when none set)
- [x] `POST /api/model-configs` (admin-protected, create config with `base_url`, `api_key`, `model_name`, `temperature`, `max_tokens`, `is_default`)
- [x] `PUT /api/model-configs/{id}` (admin-protected, partial update; promoting to default demotes all other rows)
- [x] `POST /api/model-configs/{id}/test` (admin-protected, calls the LLM via an injectable adapter — no real LLM hit in tests)
- [x] `app/models/schemas.py`: `ModelConfigListItem`, `ModelConfigDetail`, `ModelConfigCreateRequest`, `ModelConfigUpdateRequest`, `ModelConfigTestResult`
- [x] `app/adapters/llm_adapter.py`: `LLMConnectionConfig`, `LLMConnectionResult`, `ConnectionTester` Protocol-style alias, `http_test_openai_compatible_connection` (default httpx implementation), `_sanitize_error` redacts `api_key` + `base_url` from error strings
- [x] `app/services/model_config_service.py`: list / get / get_default / create / update / `test_model_connection(tester=...)`; default-exclusivity enforced via `_clear_other_defaults` (`update(is_default=False).eq("is_default", True).neq("id", new_id)` then write the new default)
- [x] `app/api/model_configs.py`: 5 routes; POST/PUT/test guarded by `Depends(require_admin_token)`; GETs public; 404s use the shared RFC 7807 body
- [x] Secret policy mirrors `mcp_servers`: list returns `has_api_key`; detail returns `masked_api_key` (`****<last4>`); plaintext `api_key` never appears in any response (asserted by `assert "sk-..." not in resp.text` across 4 tests)
- **Deliverable**: Admin can create a GLM-5 config via API, test the connection, mark it default; chat runtime (Task 7) will read the default through `get_default_model_config`.
- **Verification**: `pytest backend/tests/` → 69 passed, 16 skipped (importer integration tests requiring `UPSTREAM_PLUGINS_PATH`); `ruff check app/ tests/` clean; `openspec validate fin-agent-os --strict` pass. `test_model_connection` is exercised through an injected `tester=` callable — **no real LLM endpoint is contacted in unit or integration tests**. `pyright` not executed in sandbox (same prebuilt-node download limit hit on Tasks 4/5/6); CI to run it.

#### Known limitation — non-transactional default promotion

`update_model_config(is_default=True)` and `create_model_config(is_default=True)` clear the `is_default` flag on other rows via a separate `update(...).eq("is_default", True).neq("id", new_id)` PostgREST call **before** writing the new default row. These are two independent HTTP requests against PostgREST; they are not wrapped in a single Postgres transaction. The partial unique index `idx_model_configs_one_default` guarantees the invariant at rest, but between the two calls a concurrent admin write could observe either zero defaults (clear succeeded, insert about to run) or fail the second call (if another admin promoted a row in between).

This risk is accepted in Phase 1 because:
- `/api/model-configs` POST/PUT are guarded by `X-Admin-Token`. The shared-out-of-band token model means there is at most one concurrent admin in practice.
- The frontend marketplace will be read-only for non-admins.

Phase 2 mitigation (to revisit when admin UX gets richer or when multi-tenant admin lands): replace `_clear_other_defaults` + insert/update with a single Postgres RPC (`SECURITY DEFINER` function) that runs both statements inside one transaction, surfaced as a `rpc("set_default_model_config", ...)` call from the service layer.

#### Task 8 follow-up (test coverage) ✅

- [x] `tests/runtime/test_model_configs_api.py` extended with API-layer coverage for `POST /api/model-configs/{id}/test`:
  - `test_test_connection_requires_admin` — no `X-Admin-Token` → 401
  - `test_test_connection_missing_config` — unknown id → 404 with `code=model_config_not_found`
  - `test_test_connection_success` — monkeypatches `model_config_service.test_model_connection` to return `ok=True, latency_ms=37`; no LLM contact
  - `test_test_connection_failure_redacts_secrets` — monkeypatch returns a failure with pre-sanitized message; asserts no `sk-glm-secret`, `bigmodel`, or `openai` substrings leak through the HTTP body
- **Verification**: `pytest backend/tests/` → 73 passed, 16 skipped; `ruff check app/ tests/` clean; `openspec validate fin-agent-os --strict` pass.

#### Task 4 follow-up — Config contract cleanup v2 ✅

Tightens the env-var lifecycle contract introduced in Task 4 so that the
FastAPI runtime, importer CLIs, and migration tooling each fail (or succeed)
for the right reasons. Companion to the earlier LLM_* legacy-optional move.

- [x] `app/core/config.py`: `UPSTREAM_PLUGINS_PATH` removed from `Settings` entirely. It is an importer/operator input and was never read by any request handler; keeping it as a required `Settings` field meant `uvicorn app.main:app` refused to start during runtime-only smoke (Gate 7A) and forced operators to supply a meaningless placeholder. The Settings docstring now explicitly enumerates Runtime required / Importer-only / Migration-only / Legacy optional.
- [x] `app/importers/_cli_common.py` continues to be the single reader of `UPSTREAM_PLUGINS_PATH` (via `os.environ.get` + `MissingUpstreamPathError`); importer behavior is unchanged — `python -m app.importers.import_*` still exits status 2 with a clear message when the env var is missing or points at a non-directory.
- [x] `tests/runtime/conftest.py`: `REQUIRED_ENV` no longer sets a placeholder `UPSTREAM_PLUGINS_PATH`; both env fixtures `monkeypatch.delenv("UPSTREAM_PLUGINS_PATH")` so a developer's real `.env` cannot leak the var into runtime tests.
- [x] `tests/runtime/test_config.py`: new `test_settings_load_without_upstream_plugins_path` (Settings loads cleanly with `UPSTREAM_PLUGINS_PATH` unset and the attribute is no longer present); `test_missing_required_env_raises_clear_validation_error` updated so `UPSTREAM_PLUGINS_PATH` is now in the negative set (must NOT appear in the missing-required error message). SecretStr-no-leak invariants and the `LLM_API_KEY` SecretStr-when-set test are unchanged.
- [x] `backend/.env.example`: split into four clearly labeled blocks — Runtime required (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `INTERNAL_ADMIN_TOKEN`), Importer-only required (`UPSTREAM_PLUGINS_PATH`, commented), Migration-only required (`SUPABASE_DB_URL`, commented), Legacy optional (`LLM_*`, commented).
- [x] `backend/AGENTS.md`: Configuration section rewritten with the same four-lane structure. `UPSTREAM_PLUGINS_PATH` is documented as importer-only and `SUPABASE_DB_URL` as migration-only; neither blocks the FastAPI runtime.
- **Outcome**:
  - Runtime required env: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `INTERNAL_ADMIN_TOKEN`
  - Importer-only env: `UPSTREAM_PLUGINS_PATH` (read by `_cli_common.resolve_upstream_root()`)
  - Migration-only env: `SUPABASE_DB_URL` (consumed by psql / supabase-cli, not by FastAPI)
  - Legacy optional env: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (model_configs Supabase table is the runtime source of truth)
- **Verification**: `pytest backend/tests/runtime/test_config.py` pass; `pytest backend/tests/` → 76 passed, 16 skipped; `ruff check app/ tests/` clean; `openspec validate fin-agent-os --strict` pass.

#### Task 4 follow-up — Auth contract cleanup ✅

Documentation-only pass that locks down what `INTERNAL_ADMIN_TOKEN` /
`X-Admin-Token` actually is, before any frontend work or Phase 2 auth design
starts. No code/behavior change beyond the `app/core/deps.py` docstring.

- [x] `app/core/deps.py`: module docstring + `require_admin_token` docstring spell out the Phase 1-only contract — internal operator/admin API guard, server-side deployment secret, NOT a user-auth mechanism, NOT OAuth, NOT JWT, NOT a session token, deleted in Phase 2.
- [x] `backend/.env.example`: `INTERNAL_ADMIN_TOKEN` annotated with the same contract inline, so anyone copying the template sees the boundary before pasting a value.
- [x] `backend/AGENTS.md`: new "INTERNAL_ADMIN_TOKEN — auth contract (Phase 1 only)" subsection under Configuration enumerating lifecycle, identity, storage, transport, exclusions, and Phase 2 replacement.
- [x] `2033_fin_agent/AGENTS.md`: Auth Policy block expanded with explicit 8-point `INTERNAL_ADMIN_TOKEN` contract; covers the operator-tool-vs-public-UI distinction and the Phase 2 Supabase Auth + RBAC + RLS replacement plan.
- [x] `2033_fin_agent/README.md`: one-line summary tightened so the very first auth mention frames it as server-side operator secret, not a user-auth mechanism, with a link to the full policy.
- [x] `2033_fin_agent/frontend/AGENTS.md`: Auth (Phase 1) line rewritten — token is internal operator/admin secret; any admin/settings page that caches it in `localStorage` is an internal operator-only tool (access-restricted, not linked from public surfaces, not for production end-user flows).
- [x] `openspec/changes/fin-agent-os/design.md`:
  - Frontend route comment for `admin/settings/page.tsx` marked as internal operator-only.
  - Auth section between routes block and Decision 6 reframed (no longer says "Admin 页面通过 X-Admin-Token 保护写端点" alone — adds operator-only + Phase 2 plan).
  - Decision 7 gains an 8-point `INTERNAL_ADMIN_TOKEN` contract block; the old "前端 admin 页面让运维输入后存 localStorage" bullet is removed and replaced with a constrained 4-condition rule (operator-only doc, not for prod public UI, deploy-level access restriction, Phase 2 replacement).
- **Outcome — auth contract summary**:
  - Phase 1 only. Phase 2 deletes `INTERNAL_ADMIN_TOKEN` and `require_admin_token`.
  - Internal operator/admin API guard. Not a user-auth mechanism.
  - Server-side deployment secret (`backend/.env` locally, Fly.io secrets in prod). Shared out-of-band with operators only.
  - Sent as `X-Admin-Token`. Validated in constant time via `hmac.compare_digest`.
  - Never OAuth, JWT, session token, RBAC, or user identity.
  - Must not be exposed to ordinary end-user clients.
  - Any UI that stores it (incl. `localStorage`) is an internal operator tool — access-restricted, not on public navigation, not on the production public-user path.
  - Phase 2: Supabase Auth (JWT in `Authorization: Bearer ...`) + roles/RBAC + Postgres RLS; `chat_sessions.user_id` (currently nullable) becomes the per-user enforcement key.
- **Verification**: `rg "INTERNAL_ADMIN_TOKEN|X-Admin-Token|localStorage" 2033_fin_agent/ openspec/changes/fin-agent-os/` re-read; no remaining description frames it as a user-auth mechanism or as a token for ordinary frontend users. `openspec validate fin-agent-os --strict` pass. `ruff check app/ tests/` clean (only `app/core/deps.py` docstring touched).

### Task 7: Chat Session + Streaming Engine

- [ ] `POST /api/sessions` — create session bound to an agent, load agent's system prompt + skills + MCP tools into session context
- [ ] `POST /api/sessions/{id}/messages` — accept user message, stream agent response via SSE per Decision 8 protocol
- [ ] Implement function calling loop: model → tool_calls → execute via MCP adapter → feed results back → repeat until model stops
- [ ] Implement context window management (system prompt + history + current; truncate oldest if over limit)
- [ ] `GET /api/sessions` — list sessions
- [ ] `GET /api/sessions/{id}` — session detail + message history
- ~~`DELETE /api/sessions/{id}`~~ — **Removed.** Anonymous Phase 1 sessions have no per-user ownership, so a public destructive endpoint is unsafe. Re-introduce only behind admin-token guard (or Phase 2 Auth + RLS) with ownership checks.
- [ ] Persist all messages (user + assistant + tool_calls + tool_results) to `chat_messages`
- **Deliverable**: Full chat loop works: create session → send message → receive streaming response with tool calls
- **Verification**: curl POST creates session; curl POST sends message; SSE stream shows token/tool_call/tool_result/done events; messages persisted in DB

### Task 8: Model Config API ✅ (see block above)

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
