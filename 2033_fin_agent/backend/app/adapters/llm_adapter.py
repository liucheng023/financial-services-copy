from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

ConnectionTester = Callable[
    ["LLMConnectionConfig"],
    Awaitable["LLMConnectionResult"],
]

# Streamer signature: takes LLMStreamConfig + chat messages, yields StreamEvent.
# Defined as a Protocol-ish Callable alias so chat_service can accept either
# the real ``http_stream_chat_completion`` or a fake implementation in tests
# (the test never hits a real LLM endpoint — per AGENTS.md / Phase 1 contract).
ChatStreamer = Callable[
    ["LLMStreamConfig", list[dict[str, Any]]],
    AsyncIterator["StreamEvent"],
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


@dataclass(frozen=True)
class LLMStreamConfig:
    """Per-request streaming config built from the Supabase ``model_configs``
    row (see ``model_config_service``). The plaintext ``api_key`` lives only
    inside the request lifecycle and MUST NEVER be serialized to a client.
    """

    base_url: str
    api_key: str
    model_name: str
    temperature: float = 0.70
    max_tokens: int | None = None


# StreamEvent is the in-process representation of one chunk produced by the
# LLM. The chat_service translates these into SSE wire events
# (token / message_complete / error) per backend/AGENTS.md "Streaming Chat
# Endpoint". Tool-call events are reserved for a later task — Phase 1 Task 7
# only ships token + completion + error.
@dataclass(frozen=True)
class StreamEvent:
    type: Literal["token", "complete", "error"]
    # token: delta text
    # complete: full accumulated text (optional, services may ignore)
    # error: short human-readable message (already redacted by the adapter)
    text: str = ""
    finish_reason: str | None = None
    error_code: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


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


async def http_stream_chat_completion(
    config: LLMStreamConfig,
    messages: list[dict[str, Any]],
) -> AsyncIterator[StreamEvent]:
    url = config.base_url.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": config.model_name,
        "messages": messages,
        "stream": True,
        "temperature": config.temperature,
    }
    if config.max_tokens is not None:
        payload["max_tokens"] = config.max_tokens
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    secrets = (config.api_key, config.base_url)
    try:
        async with httpx.AsyncClient(timeout=60.0) as client, client.stream(
            "POST", url, json=payload, headers=headers
        ) as resp:
            if resp.status_code >= 400:
                yield StreamEvent(
                    type="error",
                    error_code=f"http_{resp.status_code}",
                    text=f"LLM endpoint returned HTTP {resp.status_code}",
                )
                return
            finish_reason: str | None = None
            async for raw_line in resp.aiter_lines():
                line = raw_line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choice = (chunk.get("choices") or [{}])[0]
                delta = (choice.get("delta") or {}).get("content")
                if delta:
                    yield StreamEvent(type="token", text=delta)
                fr = choice.get("finish_reason")
                if fr:
                    finish_reason = fr
            yield StreamEvent(
                type="complete",
                finish_reason=finish_reason or "stop",
            )
    except httpx.TimeoutException as exc:
        yield StreamEvent(
            type="error",
            error_code="timeout",
            text=_sanitize_error(exc, secrets=secrets),
        )
    except httpx.HTTPError as exc:
        yield StreamEvent(
            type="error",
            error_code="connection_error",
            text=_sanitize_error(exc, secrets=secrets),
        )
