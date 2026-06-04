"""Supabase client boundary.

All Supabase access in this codebase MUST go through ``get_supabase()``.
Business code in ``app/services/`` must never call ``create_client`` /
``create_async_client`` directly — that would scatter credentials and make
testing impossible.

Async choice
============
``supabase-py>=2`` exposes ``acreate_client``, which returns an
``AsyncClient`` whose ``.table(...)`` query chain is awaitable. We use that
form because every FastAPI handler in this service is async and we never
want to block the event loop on a Supabase round trip. If the installed
``supabase-py`` ever drops async support we fail at startup rather than
silently fall back to a blocking client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .config import get_settings

if TYPE_CHECKING:
    from supabase import AsyncClient


_client: AsyncClient | None = None


async def get_supabase() -> AsyncClient:
    global _client
    if _client is not None:
        return _client

    try:
        from supabase import acreate_client
    except ImportError as exc:
        raise RuntimeError(
            "supabase-py>=2 with async support is required. "
            "Install via `uv sync` (see backend/pyproject.toml)."
        ) from exc

    settings = get_settings()
    _client = await acreate_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY.get_secret_value(),
    )
    return _client


async def reset_supabase_client() -> None:
    """Test-only helper: clear the cached client."""
    global _client
    _client = None
