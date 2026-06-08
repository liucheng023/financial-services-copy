from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.supabase import get_supabase

ADMIN_HEADERS = {"X-Admin-Token": "admin-token-test-value"}

CONFIG_DEFAULT_ID = "11111111-1111-1111-1111-111111111111"
CONFIG_SECONDARY_ID = "22222222-2222-2222-2222-222222222222"

INITIAL_ROWS = [
    {
        "id": CONFIG_DEFAULT_ID,
        "slug": "glm-5-default",
        "name": "GLM-5 Default",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "sk-glm-secret-tail9999",
        "model_name": "glm-5",
        "temperature": 0.7,
        "max_tokens": 4096,
        "is_default": True,
    },
    {
        "id": CONFIG_SECONDARY_ID,
        "slug": "gpt-4o",
        "name": "GPT-4o",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-openai-secret-tail8888",
        "model_name": "gpt-4o",
        "temperature": 0.5,
        "max_tokens": 8000,
        "is_default": False,
    },
]


class _FakeResult:
    def __init__(self, data: Any) -> None:
        self.data = data


class _ModelConfigsQuery:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self._eq: list[tuple[str, Any]] = []
        self._neq: list[tuple[str, Any]] = []
        self._single = False
        self._insert: dict | None = None
        self._update: dict | None = None

    def select(self, _cols: str, **_kwargs: Any) -> _ModelConfigsQuery:
        return self

    def order(self, _field: str) -> _ModelConfigsQuery:
        return self

    def eq(self, col: str, val: Any) -> _ModelConfigsQuery:
        self._eq.append((col, val))
        return self

    def neq(self, col: str, val: Any) -> _ModelConfigsQuery:
        self._neq.append((col, val))
        return self

    def maybe_single(self) -> _ModelConfigsQuery:
        self._single = True
        return self

    def insert(self, data: dict) -> _ModelConfigsQuery:
        self._insert = data
        return self

    def update(self, data: dict) -> _ModelConfigsQuery:
        self._update = data
        return self

    def _match(self, row: dict) -> bool:
        for col, val in self._eq:
            if row.get(col) != val:
                return False
        return all(row.get(col) != val for col, val in self._neq)

    async def execute(self) -> _FakeResult:
        if self._insert is not None:
            new_id = f"new-{len(self._rows) + 1}"
            row = {"id": new_id, **self._insert}
            self._rows.append(row)
            return _FakeResult([row])

        matched = [r for r in self._rows if self._match(r)]

        if self._update is not None:
            updated_rows: list[dict] = []
            for row in matched:
                row.update(self._update)
                updated_rows.append(row)
            return _FakeResult(updated_rows)

        if self._single:
            return _FakeResult(matched[0] if matched else None)
        return _FakeResult(matched)


class FakeAsyncClient:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def table(self, name: str) -> _ModelConfigsQuery:
        if name != "model_configs":
            return _ModelConfigsQuery([])
        return _ModelConfigsQuery(self._rows)


@pytest.fixture
def api_client(env_setup) -> TestClient:
    from app.core.supabase import _reset_client_sync

    _reset_client_sync()
    rows = [dict(r) for r in INITIAL_ROWS]
    mock = FakeAsyncClient(rows)

    async def _override():
        return mock

    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_supabase] = _override
    tc = TestClient(app)
    tc.fake_rows = rows
    yield tc
    app.dependency_overrides.clear()
    _reset_client_sync()


def test_list_model_configs_masks_api_key(api_client: TestClient) -> None:
    resp = api_client.get("/api/model-configs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    for item in data:
        assert "api_key" not in item
        assert item["has_api_key"] is True
    assert "sk-glm-secret" not in resp.text
    assert "sk-openai-secret" not in resp.text


def test_get_default_model_config(api_client: TestClient) -> None:
    resp = api_client.get("/api/model-configs/default")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == CONFIG_DEFAULT_ID
    assert data["is_default"] is True
    assert "api_key" not in data
    assert data["masked_api_key"] == "****9999"
    assert "sk-glm-secret" not in resp.text


def test_get_default_returns_404_when_no_default(api_client: TestClient) -> None:
    for row in api_client.fake_rows:
        row["is_default"] = False

    resp = api_client.get("/api/model-configs/default")
    assert resp.status_code == 404
    body = resp.json()["detail"]
    assert body["code"] == "model_config_not_found"


def test_create_requires_admin(api_client: TestClient) -> None:
    resp = api_client.post(
        "/api/model-configs",
        json={
            "slug": "x",
            "name": "X",
            "base_url": "https://x",
            "api_key": "sk-x",
            "model_name": "x",
        },
    )
    assert resp.status_code == 401


def test_create_with_admin_masks_key(api_client: TestClient) -> None:
    resp = api_client.post(
        "/api/model-configs",
        json={
            "slug": "claude",
            "name": "Claude",
            "base_url": "https://api.anthropic.com/v1",
            "api_key": "sk-claude-secret-tail7777",
            "model_name": "claude-3-5-sonnet",
            "temperature": 0.3,
        },
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "claude"
    assert data["has_api_key"] is True
    assert data["masked_api_key"] == "****7777"
    assert "api_key" not in data
    assert "sk-claude-secret" not in resp.text
    assert data["is_default"] is False


def test_create_with_is_default_demotes_others(api_client: TestClient) -> None:
    resp = api_client.post(
        "/api/model-configs",
        json={
            "slug": "new-default",
            "name": "New Default",
            "base_url": "https://api.example/v1",
            "api_key": "sk-new-tail0000",
            "model_name": "new-model",
            "is_default": True,
        },
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 201
    new_data = resp.json()
    assert new_data["is_default"] is True

    old_default = next(
        r for r in api_client.fake_rows if r["id"] == CONFIG_DEFAULT_ID
    )
    assert old_default["is_default"] is False


def test_update_requires_admin(api_client: TestClient) -> None:
    resp = api_client.put(
        f"/api/model-configs/{CONFIG_SECONDARY_ID}",
        json={"name": "Renamed"},
    )
    assert resp.status_code == 401


def test_update_changes_name_and_masks_secret(api_client: TestClient) -> None:
    resp = api_client.put(
        f"/api/model-configs/{CONFIG_SECONDARY_ID}",
        json={"name": "GPT-4o Renamed"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "GPT-4o Renamed"
    assert "api_key" not in data
    assert "sk-openai-secret" not in resp.text


def test_update_promote_to_default_demotes_previous(
    api_client: TestClient,
) -> None:
    resp = api_client.put(
        f"/api/model-configs/{CONFIG_SECONDARY_ID}",
        json={"is_default": True},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    new_default = resp.json()
    assert new_default["is_default"] is True

    old_default = next(
        r for r in api_client.fake_rows if r["id"] == CONFIG_DEFAULT_ID
    )
    assert old_default["is_default"] is False


def test_update_not_found(api_client: TestClient) -> None:
    missing = "99999999-9999-9999-9999-999999999999"
    resp = api_client.put(
        f"/api/model-configs/{missing}",
        json={"name": "x"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "model_config_not_found"


# ---------------------------------------------------------------------------
# POST /api/model-configs/{id}/test
# ---------------------------------------------------------------------------


def test_test_connection_requires_admin(api_client: TestClient) -> None:
    resp = api_client.post(
        f"/api/model-configs/{CONFIG_DEFAULT_ID}/test",
    )
    assert resp.status_code == 401


def test_test_connection_missing_config(api_client: TestClient) -> None:
    resp = api_client.post(
        "/api/model-configs/00000000-0000-0000-0000-000000000000/test",
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 404
    body = resp.json()["detail"]
    assert body["code"] == "model_config_not_found"


def test_test_connection_success(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def mock_ok(*_a: object, **_k: object) -> object:
        from app.models.schemas import ModelConfigTestResult

        return ModelConfigTestResult(ok=True, latency_ms=37)

    import app.services.model_config_service as svc

    monkeypatch.setattr(svc, "test_model_connection", mock_ok)

    resp = api_client.post(
        f"/api/model-configs/{CONFIG_DEFAULT_ID}/test",
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["latency_ms"] == 37
    assert data["error_code"] is None
    assert data["error_message"] is None


def test_test_connection_failure_redacts_secrets(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def mock_fail(*_a: object, **_k: object) -> object:
        from app.models.schemas import ModelConfigTestResult

        return ModelConfigTestResult(
            ok=False,
            latency_ms=0,
            error_code="connection_error",
            error_message="ConnectError: failed to connect to ***redacted***",
        )

    import app.services.model_config_service as svc

    monkeypatch.setattr(svc, "test_model_connection", mock_fail)

    resp = api_client.post(
        f"/api/model-configs/{CONFIG_DEFAULT_ID}/test",
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["error_code"] == "connection_error"
    # Verify no plaintext secrets leaked through the HTTP response
    assert "sk-glm-secret" not in resp.text
    assert "bigmodel" not in resp.text
    assert "openai" not in resp.text
