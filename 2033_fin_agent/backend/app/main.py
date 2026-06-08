"""FastAPI entry point.

CORS + health + read-only APIs (Task 5). Chat / SSE surface ships in later
tasks. Anything that requires Supabase or LLM access goes through
``app.core.supabase`` / ``app.core.llm`` and is wired in by the owning
router, not here.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.agents import router as agents_router
from .api.health import router as health_router
from .api.mcp import router as mcp_router
from .api.model_configs import router as model_configs_router
from .api.verticals import router as verticals_router
from .core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.LOG_LEVEL.upper())

    app = FastAPI(
        title="FinAgentOS Backend",
        version="0.0.1",
        description="Phase 1 backend for the Financial Agent OS.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(agents_router)
    app.include_router(verticals_router)
    app.include_router(mcp_router)
    app.include_router(model_configs_router)
    return app


app = create_app()
