from __future__ import annotations

from typing import Any

import pytest

from app.adapters.llm_adapter import (
    LLMConnectionConfig,
    LLMConnectionResult,
    _sanitize_error,
)
from app.services import model_config_service


class _Row(dict):
    pass


class _Query:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self._single = False
        self._eq: list[tuple[str, Any]] = []

    def select(self, *_a: Any, **_k: Any) -> _Query:
        return self

    def eq(self, col: str, val: Any) -> _Query:
        self._eq.append((col, val))
        return self

    def maybe_single(self) -> _Query:
        self._single = True
        return self

    async def execute(self) -> Any:
        matched = [
            r for r in self._rows if all(r.get(c) == v for c, v in self._eq)
        ]

        class _Resp:
            data = matched[0] if (self._single and matched) else (
                None if self._single else matched
            )

        return _Resp()


class _Client:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def table(self, _name: str) -> _Query:
        return _Query(self._rows)


@pytest.mark.asyncio
async def test_test_connection_returns_none_when_config_missing() -> None:
    client = _Client([])
    result = await model_config_service.test_model_connection(
        client,  # type: ignore[arg-type]
        "missing-id",
        tester=_unused_tester,
    )
    assert result is None


@pytest.mark.asyncio
async def test_test_connection_uses_injected_tester_on_success() -> None:
    rows = [
        {
            "id": "abc",
            "base_url": "https://api.example/v1",
            "api_key": "sk-secret",
            "model_name": "glm-5",
        }
    ]
    seen: dict[str, LLMConnectionConfig] = {}

    async def fake_tester(cfg: LLMConnectionConfig) -> LLMConnectionResult:
        seen["cfg"] = cfg
        return LLMConnectionResult(ok=True, latency_ms=42)

    result = await model_config_service.test_model_connection(
        _Client(rows),  # type: ignore[arg-type]
        "abc",
        tester=fake_tester,
    )
    assert result is not None
    assert result.ok is True
    assert result.latency_ms == 42
    assert seen["cfg"].base_url == "https://api.example/v1"
    assert seen["cfg"].api_key == "sk-secret"
    assert seen["cfg"].model_name == "glm-5"


@pytest.mark.asyncio
async def test_test_connection_returns_sanitized_failure() -> None:
    rows = [
        {
            "id": "abc",
            "base_url": "https://api.example/v1",
            "api_key": "sk-secret",
            "model_name": "glm-5",
        }
    ]

    async def fake_tester(cfg: LLMConnectionConfig) -> LLMConnectionResult:
        return LLMConnectionResult(
            ok=False,
            latency_ms=11,
            error_code="connection_error",
            error_message="ConnectError: tcp dial failed",
        )

    result = await model_config_service.test_model_connection(
        _Client(rows),  # type: ignore[arg-type]
        "abc",
        tester=fake_tester,
    )
    assert result is not None
    assert result.ok is False
    assert result.error_code == "connection_error"
    assert "sk-secret" not in (result.error_message or "")


def test_sanitize_error_redacts_secrets() -> None:
    exc = RuntimeError("boom against https://api.example/v1 with sk-leak123")
    msg = _sanitize_error(exc, secrets=("sk-leak123", "https://api.example/v1"))
    assert "sk-leak123" not in msg
    assert "https://api.example/v1" not in msg
    assert "***redacted***" in msg


async def _unused_tester(_cfg: LLMConnectionConfig) -> LLMConnectionResult:
    raise AssertionError("tester must not be called when config is missing")
