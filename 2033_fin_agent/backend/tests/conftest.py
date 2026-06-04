from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture()
def upstream_plugins_root() -> Path:
    raw = os.environ.get("UPSTREAM_PLUGINS_PATH")
    if not raw:
        pytest.skip("UPSTREAM_PLUGINS_PATH not set; cannot run integration parse test")
    root = Path(raw).expanduser()
    if not root.is_dir():
        pytest.skip(f"UPSTREAM_PLUGINS_PATH={raw!r} is not a directory")
    return root
