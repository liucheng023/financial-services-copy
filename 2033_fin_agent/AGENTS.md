# Financial Agent OS — Project-Level Rules

This is the root AGENTS.md for `2033_fin_agent/`. All agents working in this repo MUST read this file first.

## Project Identity

- **Product**: Financial Agent OS — Web platform that lets B2B users use 10 financial expert agents (pitch, ma, market-research, etc.) through a chat UI
- **Inspiration**: Omniwork.ai, but vertical-specific (FSI) and Agent-centric (not chat-centric)
- **Audience**: B2B large clients, Asia-primary (Japan / Singapore / Hong Kong / China)
- **Stage**: Phase 1 — MVP foundation (basic platform with 2-3 working agents)

## Source-of-Truth Rule

**This repo contains CODE. The agent / skill / MCP DEFINITIONS live in `/root/financial_agent/plugins/`** (the original financial-services-copy repo).

- DO NOT duplicate markdown content into this repo
- Import scripts (`backend/app/importers/`) READ from `/root/financial_agent/plugins/` and write to Supabase
- Updating agent prompts → edit upstream markdown → re-run importer

## Architecture (Locked)

| Layer | Choice | Reason |
|---|---|---|
| Frontend | Next.js 14 (App Router) | Future-proof for SSR/SEO |
| Frontend deploy | Vercel | Native Next.js + global CDN |
| Backend | FastAPI (Python 3.11+) | Mature MCP library ecosystem |
| Backend deploy | Fly.io (Tokyo single region first) | Asian B2B latency |
| Database | Supabase (Postgres + Storage + Auth) | One-stop, including chat history |
| MCP adapter | mcp-use (OpenAIMCPAdapter) | Bridges MCP → OpenAI function calling |
| LLM | Model-agnostic (OpenAI-compatible API). GLM-5 first | NOT Claude-only |

**Do not change these without explicit user approval.**

## Three-Layer Plugin Model (from upstream)

This OS exposes three concepts from the upstream repo. Understand the difference:

1. **Agent** (10 total): A complete expert persona with system prompt + bundled skills + MCP access. Example: `pitch-agent` writes pitch decks.
2. **Vertical Plugin** (7 total): A domain bundle of skills + commands + MCP servers. Example: `financial-analysis` vertical owns DCF/comps skills + S&P/FactSet MCPs.
3. **MCP Server** (11 total): An external tool server. Example: `s_and_p_global_capiq` exposes company financials.

**An agent is NOT a skill.** An agent is a workflow orchestration that loads multiple skills + MCPs + a system prompt.

## Three Sources of Truth — Sync Rules

In the upstream repo:
- Skills SOURCE: `plugins/vertical-plugins/<vertical>/skills/`
- Skills BUNDLED COPIES: `plugins/agent-plugins/<agent>/skills/` (synced via `scripts/sync-agent-skills.py`)
- **Edit skills only in vertical-plugins**, then re-sync

When importing into Supabase, we treat `vertical-plugins/.../skills/` as canonical. Agent bundles are ignored to avoid drift.

## Style & Conventions

- **Comments**: English only in code. Markdown can be Chinese.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `chore:`). NEVER commit unless user explicitly asks.
- **Type safety**: NEVER use `as any`, `@ts-ignore`, `# type: ignore` to silence errors. Fix the root cause.
- **Error handling**: NEVER empty `catch {}` or bare `except: pass`.
- **Dependencies**: Prefer existing libraries. New deps require justification in PR.

## Forbidden Actions

- Modifying `/root/financial_agent/plugins/` from within `2033_fin_agent/` (upstream is read-only data source)
- Hardcoding LLM provider names. Use config-driven `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL`
- Hardcoding MCP server URLs. Read from imported `mcp_servers` table
- Skipping the importer and writing agent/skill content directly to Supabase via UI

## Phase 1 Scope (MVP)

**In scope**:
- Agent marketplace UI (browse 10 agents)
- Agent detail page (system prompt, skills, MCP tools)
- Chat with a single agent (streaming, GLM-5)
- 2-3 fully working agents (pitch, market-research, financial-analysis)
- Chat history in Supabase
- Model configuration (admin sets GLM-5 endpoint)

**Out of scope (Phase 2+)**:
- Multi-agent orchestration / collaboration
- Long-term memory across sessions
- Cookbook auto-deployment
- User-uploaded custom agents
- Billing / multi-tenancy

## How to Work in This Repo

1. Read this file (you are here)
2. Read `backend/AGENTS.md` or `frontend/AGENTS.md` depending on your task
3. Read the relevant OpenSpec change in `/root/financial_agent/openspec/changes/fin-agent-os/`
4. Check `tasks.md` for current task status
5. For agent/skill questions, read `/root/financial_agent/CLAUDE.md`

## Verification Before "Done"

- [ ] `pyright` / `tsc --noEmit` clean on changed files
- [ ] `ruff check` / `eslint` clean
- [ ] Tests pass (if test file exists)
- [ ] Manual smoke: feature works end-to-end against real backend
- [ ] No `console.log` / `print` / `// TODO` left in committed code

NO EVIDENCE = NOT DONE.
