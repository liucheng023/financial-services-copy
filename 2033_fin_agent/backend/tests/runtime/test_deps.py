from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient


def _app_with_protected_route():
    from app.core.deps import require_admin_token

    app = FastAPI()

    @app.post("/admin/ping", dependencies=[Depends(require_admin_token)])
    async def ping() -> dict[str, str]:
        return {"ok": "yes"}

    return app


def test_admin_accepts_correct_token(env_setup) -> None:
    client = TestClient(_app_with_protected_route())
    resp = client.post(
        "/admin/ping",
        headers={"X-Admin-Token": "admin-token-test-value"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": "yes"}


def test_admin_rejects_missing_token(env_setup) -> None:
    client = TestClient(_app_with_protected_route())
    resp = client.post("/admin/ping")
    assert resp.status_code == 401
    body = resp.json()["detail"]
    assert body["code"] == "admin_token_invalid"
    assert body["status"] == 401
    assert body["type"] == "about:blank"


def test_admin_rejects_wrong_token(env_setup) -> None:
    client = TestClient(_app_with_protected_route())
    resp = client.post(
        "/admin/ping",
        headers={"X-Admin-Token": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "admin_token_invalid"


def test_admin_rejects_empty_token(env_setup) -> None:
    client = TestClient(_app_with_protected_route())
    resp = client.post("/admin/ping", headers={"X-Admin-Token": ""})
    assert resp.status_code == 401
