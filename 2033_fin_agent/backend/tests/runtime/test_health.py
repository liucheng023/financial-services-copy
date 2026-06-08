from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_200(env_setup) -> None:
    from app.main import create_app

    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "fin-agent-os-backend"


def test_health_does_not_require_admin_token(env_setup) -> None:
    from app.main import create_app

    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200


def test_openapi_includes_api_routes(env_setup) -> None:
    from app.main import create_app

    client = TestClient(create_app())
    schema = client.get("/openapi.json").json()
    paths = set(schema["paths"].keys())
    assert "/health" in paths
    assert "/api/agents" in paths
    assert "/api/verticals" in paths
    assert "/api/mcp-servers" in paths
    assert "/api/model-configs" in paths
    assert "/api/model-configs/default" in paths
