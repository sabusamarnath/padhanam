"""Postgres adapter for FiredTriggersRepository (D147, S54).

Implements ``FiredTriggersRepository`` against per-tenant Postgres
data planes per D32 with bound-tenant-id defence-in-depth mirroring
the messaging Message and intake adapters.

Race-safe idempotency: ``insert_or_skip`` uses
``INSERT ... ON CONFLICT DO NOTHING`` keyed on the UNIQUE constraint
``ux_fired_triggers_tenant_user_type_key`` from Alembic 0025. The
rowcount on the resulting ``CursorResult`` distinguishes fresh-fire
(rowcount == 1) from duplicate (rowcount == 0). The check is at
database level rather than at the use-case altitude so concurrent
fires across multiple scheduler replicas (Phase 2-B+) cannot create
duplicate rows.
"""

from __future__ import annotations

from typing import Protocol
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.messaging.adapters.outbound.postgres._tables import (
    fired_triggers as fired_triggers_table,
)
from shared_kernel import TenantContext, TenantId


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresFiredTriggersAdapter:
    """Postgres adapter for the fired_triggers idempotency substrate (D147)."""

    def __init__(
        self,
        *,
        per_tenant_sessionmaker_resolver: _SessionFactoryResolver,
        bound_tenant_id: TenantId,
    ) -> None:
        self._resolve_per_tenant = per_tenant_sessionmaker_resolver
        self._bound_tenant_id = bound_tenant_id

    def _assert_bound(self, tenant_context: TenantContext) -> None:
        if str(tenant_context.tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"TenantContext.tenant_id={tenant_context.tenant_id!r} does "
                f"not match adapter's bound tenant {self._bound_tenant_id!r}; "
                "tenant-isolation defence-in-depth per D24 / D32"
            )

    async def insert_or_skip(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        trigger_type: str,
        idempotency_key: str | None,
    ) -> bool:
        """Race-safe insert; True on fresh fire, False on duplicate.

        Uses INSERT ... ON CONFLICT DO NOTHING on the UNIQUE
        constraint ``(tenant_id, user_id, trigger_type,
        idempotency_key)``. The rowcount on the resulting cursor
        distinguishes the two outcomes per psycopg semantics.
        """
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(
            TenantId(str(self._bound_tenant_id))
        )
        async with sessionmaker() as session:
            stmt = pg.insert(fired_triggers_table).values(
                id=str(uuid4()),
                tenant_id=tenant_context.tenant_id,
                user_id=user_id,
                trigger_type=trigger_type,
                idempotency_key=idempotency_key,
            )
            stmt = stmt.on_conflict_do_nothing(
                constraint="ux_fired_triggers_tenant_user_type_key"
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount == 1


__all__ = ["PostgresFiredTriggersAdapter"]
