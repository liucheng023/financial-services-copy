"""FastAPI dependencies — only cross-cutting concerns belong here.

Currently exposes the ``require_admin_token`` guard used on every Phase 1
write endpoint. Errors follow the RFC 7807 problem-details shape declared
in backend/AGENTS.md so the frontend can branch on ``code`` and display
``detail``.
"""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from .config import Settings, get_settings


def _problem(*, http_status: int, code: str, title: str, detail: str) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={
            "type": "about:blank",
            "title": title,
            "status": http_status,
            "code": code,
            "detail": detail,
        },
    )


async def require_admin_token(
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    settings: Settings = None,  # type: ignore[assignment]
) -> None:
    if settings is None:
        settings = get_settings()

    expected = settings.INTERNAL_ADMIN_TOKEN.get_secret_value()

    if x_admin_token is None or not hmac.compare_digest(x_admin_token, expected):
        raise _problem(
            http_status=status.HTTP_401_UNAUTHORIZED,
            code="admin_token_invalid",
            title="Admin token required",
            detail="A valid X-Admin-Token header is required for this endpoint.",
        )
