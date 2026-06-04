"""Shared CLI helpers for importer scripts.

Centralizes ``UPSTREAM_PLUGINS_PATH`` resolution so every importer
(``import_agents.py``, ``import_skills.py``, etc.) fails the same way with
the same message when the env var is missing or points at a bad path.
"""

from __future__ import annotations

import os
from pathlib import Path

UPSTREAM_ENV_VAR = "UPSTREAM_PLUGINS_PATH"


class MissingUpstreamPathError(RuntimeError):
    pass


def resolve_upstream_root() -> Path:
    raw = os.environ.get(UPSTREAM_ENV_VAR)
    if not raw:
        raise MissingUpstreamPathError(
            f"Environment variable {UPSTREAM_ENV_VAR} is not set. "
            "Point it at the upstream `plugins/` directory of the "
            "anthropics/financial-services repo."
        )
    root = Path(raw).expanduser()
    if not root.is_dir():
        raise MissingUpstreamPathError(
            f"{UPSTREAM_ENV_VAR}={raw!r} is not an existing directory."
        )
    return root


def supabase_env_available() -> bool:
    return bool(os.environ.get("SUPABASE_URL")) and bool(
        os.environ.get("SUPABASE_SERVICE_KEY")
    )
