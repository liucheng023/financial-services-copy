"""Liveness probe.

Returns 200 unconditionally — used by Fly.io health checks and by
frontend integration smoke tests. MUST stay free of Supabase / LLM
calls so a downstream outage cannot mark the service unhealthy.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "fin-agent-os-backend"}
