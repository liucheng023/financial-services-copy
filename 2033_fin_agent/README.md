# Financial Agent OS

B2B web platform for financial expert agents. Asia-primary. Phase 1 MVP.

## Quick Links

- **Project rules**: [AGENTS.md](./AGENTS.md)
- **Backend rules**: [backend/AGENTS.md](./backend/AGENTS.md)
- **Frontend rules**: [frontend/AGENTS.md](./frontend/AGENTS.md)
- **Spec & tasks**: `openspec/changes/fin-agent-os/` (repo-root relative)
- **Upstream content**: agents/skills/MCPs live in the upstream `anthropics/financial-services` repo. Path is configured via the `UPSTREAM_PLUGINS_PATH` env var — set it to the local `plugins/` directory.

## Architecture

```
┌──────────────┐       ┌──────────────┐       ┌────────────┐
│  Next.js     │ HTTPS │  FastAPI     │ MCP   │  External  │
│  (Vercel)    │ ────▶ │  (Fly.io     │ ────▶ │  MCP       │
│              │       │   Tokyo)     │       │  Servers   │
└──────────────┘       └──────┬───────┘       └────────────┘
       │                      │
       │                      │ OpenAI-compatible
       │                      ▼
       │               ┌──────────────┐
       │               │  GLM-5 /     │
       │               │  any LLM     │
       │               └──────────────┘
       │                      │
       └──────────┬───────────┘
                  ▼
           ┌──────────────┐
           │  Supabase    │
           │  (Postgres + │
           │   Storage)   │
           └──────────────┘
```

Phase 1: no end-user auth. Admin endpoints protected by `X-Admin-Token`. Phase 2 will introduce Supabase Auth.

## Phase 1 Goal

Ship a working web platform where a B2B user can:
1. Browse 10 financial agents
2. Click into an agent, see its skills/MCPs/system prompt
3. Start a chat, get streaming responses
4. See chat history persisted
5. Admin configures GLM-5 endpoint

## Status

- [x] Spec written (openspec `fin-agent-os` change)
- [x] Architecture locked (this directory)
- [x] AGENTS.md three-layer written
- [ ] Backend skeleton
- [ ] Frontend skeleton
- [ ] Supabase schema + importers
- [ ] First end-to-end chat
