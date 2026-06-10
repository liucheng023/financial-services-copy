import { apiClient } from "@/lib/api/client";
import type { AgentListItem } from "@/lib/api/types";

// Agent list comes from the backend and is not known at build time.
// Render on demand so prerender doesn't try to reach the backend during `next build`.
export const dynamic = "force-dynamic";

async function getAgents(): Promise<AgentListItem[]> {
  return apiClient.GET<AgentListItem[]>("/api/agents");
}

export default async function AgentsPage() {
  const agents = await getAgents();

  return (
    <div className="p-6 max-w-5xl">
      <h2 className="text-2xl font-bold mb-6">Financial Expert Agents</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {agents.map((agent) => (
          <a
            key={agent.slug}
            href={`/agents/${agent.slug}/chat`}
            className="block p-4 rounded-lg border border-zinc-800 hover:border-zinc-600 hover:bg-zinc-900 transition-colors"
          >
            <h3 className="font-semibold text-zinc-100">{agent.name}</h3>
            {agent.description && (
              <p className="text-sm text-zinc-400 mt-1 line-clamp-2">
                {agent.description}
              </p>
            )}
            <div className="mt-2 flex gap-3 text-xs text-zinc-500">
              <span>{agent.skill_count} skills</span>
              <span>{agent.mcp_count} MCPs</span>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
