"""FastAPI dependencies — only cross-cutting concerns belong here.

Currently exposes the ``require_admin_token`` guard used on every Phase 1
write/sensitive endpoint. Errors follow the RFC 7807 problem-details shape
declared in backend/AGENTS.md so the frontend can branch on ``code`` and
display ``detail``.

Auth contract (Phase 1 only, see ``2033_fin_agent/AGENTS.md`` "Auth Policy"):

* ``INTERNAL_ADMIN_TOKEN`` is an internal operator/admin API guard. It is
  a server-side deployment secret (``backend/.env`` locally, Fly.io secrets
  in prod). It is NOT a user authentication mechanism, NOT OAuth, NOT JWT,
  NOT a session token, and MUST NOT be exposed to or persisted by ordinary
  end-user clients.
* The guard exists only to prevent accidental writes during the MVP and to
  scope import / model-config / mcp-config endpoints to operators.
* Phase 2 replaces this entirely with Supabase Auth (JWT in
  ``Authorization: Bearer ...``) plus roles/RBAC and Postgres RLS. The
  ``require_admin_token`` dependency will be deleted at that time.
"""

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

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
    settings: Settings = Depends(get_settings),
) -> None:
    """Phase 1 operator guard. See module docstring for the auth contract.

    Validates ``X-Admin-Token`` against ``INTERNAL_ADMIN_TOKEN`` in constant
    time. NOT a user-auth mechanism; Phase 2 replaces with Supabase Auth.
    """
    expected = settings.INTERNAL_ADMIN_TOKEN.get_secret_value()

    if x_admin_token is None or not hmac.compare_digest(x_admin_token, expected):
        raise _problem(
            http_status=status.HTTP_401_UNAUTHORIZED,
            code="admin_token_invalid",
            title="Admin token required",
            detail="A valid X-Admin-Token header is required for this endpoint.",
        )
