from __future__ import annotations

from typing import TYPE_CHECKING

from ..adapters.llm_adapter import (
    ConnectionTester,
    LLMConnectionConfig,
    http_test_openai_compatible_connection,
)
from ..models.schemas import (
    ModelConfigCreateRequest,
    ModelConfigDetail,
    ModelConfigListItem,
    ModelConfigTestResult,
    ModelConfigUpdateRequest,
)
from .agent_service import _mask_api_key

if TYPE_CHECKING:
    from supabase import AsyncClient


async def list_model_configs(client: AsyncClient) -> list[ModelConfigListItem]:
    resp = await (
        client.table("model_configs")
        .select("id,slug,name,base_url,model_name,is_default,api_key")
        .order("name")
        .execute()
    )
    items: list[ModelConfigListItem] = []
    for r in resp.data or []:
        has_key, _ = _mask_api_key(r.get("api_key"))
        items.append(
            ModelConfigListItem(
                id=str(r["id"]),
                slug=r["slug"],
                name=r["name"],
                base_url=r["base_url"],
                model_name=r["model_name"],
                is_default=bool(r.get("is_default", False)),
                has_api_key=has_key,
            )
        )
    return items


async def get_model_config(
    client: AsyncClient, config_id: str
) -> ModelConfigDetail | None:
    resp = await (
        client.table("model_configs")
        .select("*")
        .eq("id", config_id)
        .maybe_single()
        .execute()
    )
    row = resp.data
    if not row:
        return None
    return _detail_from_row(row)


async def get_default_model_config(
    client: AsyncClient,
) -> ModelConfigDetail | None:
    resp = await (
        client.table("model_configs")
        .select("*")
        .eq("is_default", True)
        .maybe_single()
        .execute()
    )
    row = resp.data
    if not row:
        return None
    return _detail_from_row(row)


async def create_model_config(
    client: AsyncClient, req: ModelConfigCreateRequest
) -> ModelConfigDetail:
    row_data = {
        "slug": req.slug,
        "name": req.name,
        "base_url": req.base_url,
        "api_key": req.api_key,
        "model_name": req.model_name,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "is_default": req.is_default,
    }
    if req.is_default:
        await _clear_other_defaults(client, exclude_id=None)

    resp = await client.table("model_configs").insert(row_data).execute()
    created = resp.data[0] if resp.data else {}
    return _detail_from_row(created)


async def update_model_config(
    client: AsyncClient,
    config_id: str,
    req: ModelConfigUpdateRequest,
) -> ModelConfigDetail | None:
    existing = await get_model_config(client, config_id)
    if existing is None:
        return None

    updates: dict = {}
    for field in ("name", "base_url", "model_name", "temperature", "max_tokens"):
        val = getattr(req, field, None)
        if val is not None:
            updates[field] = val
    if req.api_key is not None:
        updates["api_key"] = req.api_key
    if req.is_default is not None:
        updates["is_default"] = req.is_default

    if not updates:
        return existing

    if req.is_default is True:
        await _clear_other_defaults(client, exclude_id=config_id)

    resp = (
        await client.table("model_configs")
        .update(updates)
        .eq("id", config_id)
        .execute()
    )
    row = resp.data[0] if resp.data else {}
    return _detail_from_row(row)


async def test_model_connection(
    client: AsyncClient,
    config_id: str,
    *,
    tester: ConnectionTester | None = None,
) -> ModelConfigTestResult | None:
    resp = await (
        client.table("model_configs")
        .select("base_url,api_key,model_name")
        .eq("id", config_id)
        .maybe_single()
        .execute()
    )
    row = resp.data
    if not row:
        return None

    cfg = LLMConnectionConfig(
        base_url=row["base_url"],
        api_key=row["api_key"],
        model_name=row["model_name"],
    )
    run = tester or http_test_openai_compatible_connection
    result = await run(cfg)
    return ModelConfigTestResult(
        ok=result.ok,
        latency_ms=result.latency_ms,
        error_code=result.error_code,
        error_message=result.error_message,
    )


async def _clear_other_defaults(
    client: AsyncClient, *, exclude_id: str | None
) -> None:
    query = client.table("model_configs").update({"is_default": False}).eq(
        "is_default", True
    )
    if exclude_id is not None:
        query = query.neq("id", exclude_id)
    await query.execute()


def _detail_from_row(row: dict) -> ModelConfigDetail:
    has_key, masked = _mask_api_key(row.get("api_key"))
    return ModelConfigDetail(
        id=str(row["id"]),
        slug=row["slug"],
        name=row["name"],
        base_url=row["base_url"],
        model_name=row["model_name"],
        is_default=bool(row.get("is_default", False)),
        temperature=float(row.get("temperature", 0.70)),
        max_tokens=row.get("max_tokens"),
        has_api_key=has_key,
        masked_api_key=masked,
    )
