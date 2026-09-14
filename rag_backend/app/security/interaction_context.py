"""HTTP/Agent 入口共用的交互安全生命周期。"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Mapping

from fastapi import HTTPException

from app.security.interaction_safety import (
    InteractionHandle,
    InteractionSafetyGuard,
    SafetyAbort,
    interaction_guard,
)


def _blocked_http_error(exc: SafetyAbort) -> HTTPException:
    status = 429 if exc.decision.score < 8 else 403
    return HTTPException(status_code=status, detail="请求触发安全策略，已终止处理")


@asynccontextmanager
async def guarded_interaction(
    interaction_id: str,
    principal_id: str,
    tenant_id: str,
    query: str,
    *,
    history_items: int = 0,
    metadata: Mapping[str, object] | None = None,
    guard: InteractionSafetyGuard = interaction_guard,
) -> AsyncIterator[InteractionHandle]:
    """统一处理交互开始、异常收敛和审计收尾。"""
    try:
        handle = await guard.start(
            interaction_id,
            principal_id,
            tenant_id,
            query,
            history_items=history_items,
            metadata=dict(metadata or {}),
        )
    except SafetyAbort as exc:
        raise _blocked_http_error(exc) from exc

    try:
        yield handle
    except asyncio.CancelledError:
        await guard.finish(interaction_id, "cancelled")
        raise
    except SafetyAbort:
        await guard.finish(interaction_id, "blocked")
        raise
    except Exception:
        await guard.finish(interaction_id, "failed")
        raise
    else:
        await guard.finish(interaction_id, "completed")


@asynccontextmanager
async def prepare_stream_interaction(
    interaction_id: str,
    principal_id: str,
    tenant_id: str,
    query: str,
    *,
    history_items: int = 0,
    metadata: Mapping[str, object] | None = None,
    guard: InteractionSafetyGuard = interaction_guard,
) -> AsyncIterator[InteractionHandle]:
    """保护流式响应准备阶段，成功后由响应生成器负责最终收尾。"""
    try:
        handle = await guard.start(
            interaction_id,
            principal_id,
            tenant_id,
            query,
            history_items=history_items,
            metadata=dict(metadata or {}),
        )
    except SafetyAbort as exc:
        raise _blocked_http_error(exc) from exc

    try:
        yield handle
    except asyncio.CancelledError:
        await guard.finish(interaction_id, "cancelled")
        raise
    except SafetyAbort:
        await guard.finish(interaction_id, "blocked")
        raise
    except HTTPException as exc:
        await guard.finish(interaction_id, "blocked" if exc.status_code < 500 else "failed")
        raise
    except Exception:
        await guard.finish(interaction_id, "failed")
        raise


async def validate_interaction_input(
    interaction_id: str,
    principal_id: str,
    tenant_id: str,
    query: str,
    *,
    metadata: Mapping[str, object] | None = None,
    guard: InteractionSafetyGuard = interaction_guard,
) -> None:
    """为后台任务做入口检查；通过后立即收尾，不追踪跨进程执行状态。"""
    async with guarded_interaction(
        interaction_id,
        principal_id,
        tenant_id,
        query,
        metadata=metadata,
        guard=guard,
    ):
        pass
