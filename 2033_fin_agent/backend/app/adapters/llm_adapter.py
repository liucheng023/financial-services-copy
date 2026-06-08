from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

ConnectionTester = Callable[
    ["LLMConnectionConfig"],
    Awaitable["LLMConnectionResult"],
]


@dataclass(frozen=True)
class LLMConnectionConfig:
    base_url: str
    api_key: str
    model_name: str


@dataclass(frozen=True)
class LLMConnectionResult:
    ok: bool
    latency_ms: int
    error_code: str | None = None
    error_message: str | None = None


def _sanitize_error(exc: BaseException, *, secrets: tuple[str, ...]) -> str:
    raw = f"{type(exc).__name__}: {exc}"
    redacted = raw
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***redacted***")
    return redacted[:300]


async def http_test_openai_compatible_connection(
    config: LLMConnectionConfig,
) -> LLMConnectionResult:
    url = config.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": config.model_name,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    secrets = (config.api_key, config.base_url)
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
        latency_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code >= 400:
            return LLMConnectionResult(
                ok=False,
                latency_ms=latency_ms,
                error_code=f"http_{resp.status_code}",
                error_message=f"LLM endpoint returned HTTP {resp.status_code}",
            )
        return LLMConnectionResult(ok=True, latency_ms=latency_ms)
    except httpx.TimeoutException as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return LLMConnectionResult(
            ok=False,
            latency_ms=latency_ms,
            error_code="timeout",
            error_message=_sanitize_error(exc, secrets=secrets),
        )
    except httpx.HTTPError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return LLMConnectionResult(
            ok=False,
            latency_ms=latency_ms,
            error_code="connection_error",
            error_message=_sanitize_error(exc, secrets=secrets),
        )
