# FinAgentOS Frontend — Chat MVP

Next.js 14 (App Router) web client for **Financial Agent OS**. Phase 1 ships the chat MVP:
browse 10 financial expert agents, click into one, start a chat, and stream the LLM
response token-by-token from the FastAPI backend.

For project-wide rules read [`../AGENTS.md`](../AGENTS.md). For frontend conventions
(stack, state, styling, forbidden patterns) read [`./AGENTS.md`](./AGENTS.md). This
README is the runtime contract — how to run it and what it depends on.

## Backend Dependency

The frontend is a thin client. It does **not** talk to Supabase, **does not** call any
LLM, and **does not** hold any secrets.

- The FastAPI backend (`../backend/`) must be running and reachable.
- The backend owns: Supabase reads/writes, LLM calls (GLM-5 / any OpenAI-compatible
  provider), MCP tool execution, chat session persistence, SSE streaming.
- The frontend only knows one URL: `NEXT_PUBLIC_BACKEND_URL`.

## Local Run

```bash
# 1. Install dependencies (lockfile: package-lock.json)
npm install

# 2. Point at the backend (default if unset: http://localhost:8000)
export NEXT_PUBLIC_BACKEND_URL=http://localhost:8001

# 3. Start the dev server on :3000
npm run dev
```

Open <http://localhost:3000/agents>, click an agent card, send a message.

## Environment Variables

Phase 1 frontend has **exactly one** env var:

| Name | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | yes (defaults to `http://localhost:8000`) | FastAPI backend base URL |

The frontend **must not** be configured with any of the following — these are
backend-only or operator-only:

- `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` — frontend does not
  access Supabase directly in Phase 1.
- `SUPABASE_SERVICE_KEY` — backend deployment secret.
- `LLM_API_KEY` / GLM-5 API key / any model provider key — backend only.
- `INTERNAL_ADMIN_TOKEN` — backend deployment secret guarding internal operator/admin
  endpoints; it is **not** a user-auth mechanism and **must not** appear in the
  ordinary chat UI or any public end-user route.

See [`./AGENTS.md` → Environment Variables](./AGENTS.md#environment-variables) for the
full rules.

## Verification Commands

Use `npm run` exclusively. Do not invoke `pnpm` or `yarn` — `package-lock.json` is the
authoritative lockfile.

```bash
npm run lint        # ESLint via next lint
npm run typecheck   # tsc --noEmit (strict)
npm run test        # Vitest unit tests (SSE parser)
npm run build       # Next.js production build
```

All four must pass before opening a PR.

## Known Limitations (Phase 1)

- **Session id is page-state only.** Reloading the chat page starts a new session;
  the previous session row stays in Supabase but the UI does not restore it. (Routing
  sessions through the URL is a Phase 2 follow-up.)
- **No DELETE session UI.** The backend has no delete endpoint by design.
- **No `tool_call` / `tool_result` rendering.** The Phase 1 backend never emits these
  SSE events; tool-use UI lands when the backend wires MCP execution into the chat
  flow.
- **No admin/operator UI in this build.** `INTERNAL_ADMIN_TOKEN` belongs to a separate
  internal operator tool, not the chat UI.
- **No end-user authentication.** Phase 1 sessions are anonymous. Phase 2 will add
  Supabase Auth + RBAC + RLS and tie sessions to authenticated users.

## Files of Note

- `lib/api/client.ts` — typed `fetch` wrapper (`GET` / `POST` / `POST_SSE`) with
  RFC 7807 error unwrapping.
- `lib/api/types.ts` — TypeScript mirror of the backend contract.
- `lib/chat/sse-parser.ts` — SSE event parser + `ReadableStream` consumer (UTF-8 safe
  across chunk boundaries).
- `lib/chat/sse-parser.test.ts` — Vitest unit tests for the parser.
- `stores/chat-store.ts` — Zustand store for messages + streaming buffer.
- `app/agents/page.tsx` — server component, agent list.
- `app/agents/[slug]/chat/page.tsx` — client component, chat with SSE streaming.
