# Frontend — Next.js Web App

This is `frontend/AGENTS.md`. Read root `../AGENTS.md` first.

## Stack

- **Framework**: Next.js 14 (App Router, NOT Pages Router)
- **Language**: TypeScript strict mode (no `any`, no implicit `any`)
- **Styling**: Tailwind CSS + shadcn/ui components
- **State**:
  - Server state: TanStack Query (React Query v5)
  - Client state: Zustand (NOT Redux, NOT Context for app state)
  - URL state: `nuqs` or native `useSearchParams`
- **Forms**: react-hook-form + zod validation
- **API client**: Generated from backend OpenAPI via `openapi-typescript`
- **Auth (Phase 1)**: NONE for end users. No login UI, no Supabase Auth in Phase 1. The only protected endpoints are the internal operator/admin APIs (imports, MCP config, model config), which are guarded by the `X-Admin-Token` header backed by the server-side `INTERNAL_ADMIN_TOKEN` deployment secret. **`INTERNAL_ADMIN_TOKEN` is NOT a user-auth mechanism, NOT OAuth, NOT JWT, and MUST NOT be exposed to ordinary end-user clients.** Any admin/settings page that lets an operator paste this token (and optionally caches it in `localStorage` purely as a dev/MVP convenience) is an **internal operator-only tool** — it must be access-restricted, never linked from the public end-user surface (marketplace, chat), and never relied on for production end-user flows. Phase 2 replaces all of this with Supabase Auth (`@supabase/ssr`) + RBAC + RLS and removes the admin-token surface entirely.
- **Streaming**: `fetch` + `ReadableStream` for SSE (NOT native `EventSource`; our chat endpoint is POST)
- **Package manager**: pnpm
- **Lint**: ESLint + Prettier

## Directory Structure

```
frontend/
├── app/                         # App Router pages
│   ├── layout.tsx               # Root layout (sidebar + main)
│   ├── page.tsx                 # Home → redirects to /agents
│   ├── agents/
│   │   ├── page.tsx             # Agent marketplace
│   │   └── [slug]/
│   │       ├── page.tsx         # Agent detail (workflow config view)
│   │       └── chat/
│   │           └── page.tsx     # Chat with this agent
│   ├── verticals/page.tsx
│   ├── mcp-servers/page.tsx
│   ├── admin/
│   │   └── settings/page.tsx    # Model config (GLM-5 endpoint, etc.)
│   └── api/                     # Next API routes (Phase 1: empty; reserved for Phase 2 auth callback)
├── components/
│   ├── ui/                      # shadcn primitives
│   ├── layout/                  # Sidebar, Header
│   ├── agent/                   # AgentCard, AgentDetail, etc.
│   ├── chat/                    # ChatWindow, MessageList, StreamingMessage
│   └── mcp/
├── lib/
│   ├── api/                     # Typed API client (generated)
│   ├── supabase/                # Supabase client (server + browser)
│   ├── chat/                    # SSE chat hook
│   └── utils.ts                 # cn(), formatters
├── stores/                      # Zustand stores
│   ├── chat-store.ts
│   └── ui-store.ts
├── types/                       # Hand-written types (NOT generated)
├── public/
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

## Rendering Strategy

- **Default**: Server Components (RSC)
- **Use `'use client'` only when needed**: hooks, browser APIs, event handlers, state
- **Phase 1 reality**: Chat UI is heavily interactive → most of `/agents/[slug]/chat` is client. Marketplace/detail pages → mostly server.
- **Data fetching**:
  - Server Components → fetch directly in component (await fetch with cache config)
  - Client Components → TanStack Query
- **Never** mix server data props passed deep into client trees. Fetch in client component instead.

## API Client

Generated from backend `/openapi.json`:

```bash
pnpm run generate-api  # Runs openapi-typescript against backend
```

Output: `lib/api/types.ts` + `lib/api/client.ts` (typed `fetch` wrapper)

Usage:

```typescript
import { apiClient } from "@/lib/api/client";

const agents = await apiClient.GET("/agents");  // Fully typed
```

**NEVER** hand-write API response types. **NEVER** call `fetch` directly outside `lib/api/`.

## State Management Rules

| What | Where |
|---|---|
| Server data (agents, chat history) | TanStack Query |
| Current chat session messages | Zustand (`chat-store`) |
| Sidebar open/closed | Zustand (`ui-store`) |
| Selected agent in marketplace | URL param (`?agent=slug`) |
| Form input | react-hook-form |
| Theme | next-themes |

**Forbidden**: useContext for app state, prop drilling > 2 levels, useState for shared state across routes.

## Chat Streaming Pattern

`EventSource` (native browser API) only supports GET. Our chat endpoint is `POST /api/sessions/{id}/messages` (body carries the message). Therefore use `fetch` with `ReadableStream` for SSE parsing, NOT native `EventSource`.

```typescript
// lib/chat/use-chat-stream.ts
import { useState } from "react";

type SseEvent =
  | { type: "message_start"; message_id: string; session_id: string }
  | { type: "token"; delta: string }
  | { type: "tool_call"; tool_call_id: string; tool: string; args: unknown }
  | { type: "tool_result"; tool_call_id: string; result: string; is_error: boolean }
  | { type: "message_complete"; message_id: string; finish_reason: string }
  | { type: "error"; code: string; message: string; recoverable: boolean }
  | { type: "done" };

export function useChatStream(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);

  const send = async (content: string) => {
    setStreaming(true);
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/sessions/${sessionId}/messages`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      }
    );
    if (!res.ok || !res.body) {
      // Non-2xx happens BEFORE the stream starts (e.g., session not found, validation)
      throw await parseHttpError(res);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // Split by SSE event delimiter "\n\n"
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const raw of parts) {
        const evt = parseSseEvent(raw); // parse "event: x\ndata: {...}" -> SseEvent
        handle(evt);
      }
    }
    setStreaming(false);
  };

  return { messages, streaming, send };
}
```

The chat session itself is created via `POST /api/sessions` (returns `{id, agent_slug, ...}`) BEFORE the first message. Frontend keeps `sessionId` in URL or Zustand.

## Styling Conventions

- **Tailwind utility-first**. NO custom CSS files (except `globals.css` for resets).
- **Use shadcn/ui** for buttons, inputs, dialogs, dropdowns. Don't reinvent.
- **Layout**: Persistent sidebar (sections: Experts / Skills / Verticals / MCPs / Settings) + main content area
- **Dark mode**: Required from day 1. Use `next-themes`.
- **Responsive**: Desktop-first (B2B users on laptops), but should not break on tablet. Mobile is Phase 2.

## Component Rules

- **One component per file**. Filename = component name in kebab-case (`agent-card.tsx` exports `AgentCard`).
- **Props**: Always typed with named interface (`AgentCardProps`), not inline.
- **No default exports** except for Next.js `page.tsx` / `layout.tsx` (Next requires it).
- **Server vs Client boundary**: Place `'use client'` at the smallest possible scope. Pass server-fetched data as props.

## Forbidden

- `any` type — use `unknown` + narrow, or fix the type
- `// @ts-ignore` / `// @ts-expect-error` — fix the actual issue
- Direct DOM manipulation (`document.getElementById`) — use refs
- Inline styles (`style={{...}}`) — use Tailwind classes
- `useEffect` for data fetching — use TanStack Query or RSC
- `console.log` in committed code — use proper logger or remove
- Putting backend URLs in client code as literals — use `NEXT_PUBLIC_BACKEND_URL`

## Environment Variables

```bash
NEXT_PUBLIC_BACKEND_URL=https://api.example.com   # FastAPI on Fly.io
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...

# Server-only (not exposed)
SUPABASE_SERVICE_ROLE_KEY=...  # Only if needed for server actions
```

`NEXT_PUBLIC_*` is bundled into client. NEVER put secrets there.

## Dev Loop

```bash
pnpm install
pnpm dev               # Next.js dev server on :3000
pnpm lint
pnpm typecheck         # tsc --noEmit
pnpm test              # Vitest (Phase 1: minimal)
pnpm generate-api      # Re-generate API types from backend
pnpm build             # Production build (check before PR)
```

## Deployment (Vercel)

- Connected to GitHub repo, auto-deploys on push to `main`
- Preview deploys on every PR
- Env vars set in Vercel dashboard (NOT in `.env`)
- Build command: `pnpm build` (default)
- Output: `.next` (default)
- Edge runtime: NOT used in Phase 1 (Node.js runtime is fine, we don't need edge for B2B)

## What Belongs Here vs Backend

- **Frontend**: UI rendering, optimistic updates, form validation (display), URL state, theme
- **Backend**: ALL business logic, LLM calls, MCP calls, DB writes, auth verification, agent orchestration
- **Shared**: Types generated from OpenAPI (one-way: backend → frontend)

## Verification Before "Done"

- [ ] `pnpm typecheck` clean
- [ ] `pnpm lint` clean
- [ ] `pnpm build` succeeds
- [ ] Feature works in browser against real backend
- [ ] No layout shift / hydration mismatch in console
- [ ] Dark mode looks correct
