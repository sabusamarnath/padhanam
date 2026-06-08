"""Tenant isolation contract for the tasks substrate (D24, D167, S65).

The task_connections and tasks tables are tenant-scoped per database-per-tenant
(D32). The Postgres adapters carry bound-tenant defence-in-depth: an adapter
bound to tenant A rejects any call carrying tenant B's TenantContext before
session resolution (the calendar/email precedent). Structural — no database; the
live tenant_b-reads-empty check is the operator-gated pull at the smoke.

D24 requires every adapter touching tenant-scoped data to ship with
tenant_isolation contract scenarios.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from shared_kernel import TenantContext, TenantId

from contexts.tasks.adapters.outbound.postgres.connection_repository import (
    PostgresConnectionRepository,
)
from contexts.tasks.adapters.outbound.postgres.task_store import PostgresTaskStore
from contexts.tasks.domain.connection import Connection
from contexts.tasks.domain.task import Task, TaskStatus

_NOW = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
_TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _ctx(tenant: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant, jurisdiction="eu-west", cost_attribution_id=tenant
    )


async def _unreachable_resolver(_tenant_id: TenantId) -> object:  # noqa: ARG001
    raise AssertionError("resolver must not be reached on bound-tenant reject")


def _task(tenant: str) -> Task:
    return Task(
        id=uuid4(),
        tenant_id=UUID(tenant),
        jurisdiction="eu-west",
        google_task_id="t-1",
        tasklist_id="L1",
        tasklist_title="My Tasks",
        status=TaskStatus.NEEDS_ACTION,
        title="x",
        notes=None,
        due_at=None,
        completed_at=None,
        parent=None,
        position=None,
        source_updated_at=None,
        content_hash="h",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _connection(tenant: str) -> Connection:
    return Connection(
        id=uuid4(),
        tenant_id=UUID(tenant),
        jurisdiction="eu-west",
        provider="google_tasks",
        provider_config_key="google-tasks",
        provider_connection_ref="ref",
        created_at=_NOW,
        updated_at=_NOW,
    )


def test_task_store_rejects_cross_tenant_upsert() -> None:
    store = PostgresTaskStore(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId(_TENANT_A),
    )
    with pytest.raises(ValueError, match="does not match adapter's bound tenant"):
        asyncio.run(
            store.upsert_task(tenant_context=_ctx(_TENANT_B), task=_task(_TENANT_B))
        )


def test_task_store_rejects_cross_tenant_read() -> None:
    store = PostgresTaskStore(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId(_TENANT_A),
    )
    with pytest.raises(ValueError, match="does not match adapter's bound tenant"):
        asyncio.run(
            store.list_tasks(tenant_context=_ctx(_TENANT_B))
        )


def test_task_connection_repo_rejects_cross_tenant() -> None:
    repo = PostgresConnectionRepository(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId(_TENANT_A),
    )
    with pytest.raises(ValueError, match="bound-tenant mismatch"):
        asyncio.run(
            repo.save_connection(
                tenant_context=_ctx(_TENANT_B), connection=_connection(_TENANT_B)
            )
        )
