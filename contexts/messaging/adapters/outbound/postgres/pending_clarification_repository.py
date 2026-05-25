"""Postgres adapter for PendingClarificationRepository (D134, S47).

Implements ``PendingClarificationRepository`` against per-tenant
Postgres data planes per D32 with the same bound-tenant-id defence-
in-depth as the messaging Message and intake repositories.

``proposed_intent`` rides as JSONB; the migration's partial unique
index on ``(tenant_id, user_id) WHERE status = 'PENDING'`` enforces
the D134 invariant structurally — the create use case respects it
operationally by expiring any prior PENDING before inserting a new
one.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.messaging.adapters.outbound.postgres._tables import (
    pending_clarifications as pending_table,
)
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
    PendingClarificationStatus,
)
from shared_kernel import TenantContext, TenantId


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresPendingClarificationRepository:
    """Postgres adapter for the PendingClarification aggregate (D134)."""

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

    def _assert_entity_tenant(self, entity_tenant_id: object) -> None:
        if str(entity_tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"PendingClarification.tenant_id={entity_tenant_id!r} does "
                f"not match adapter's bound tenant {self._bound_tenant_id!r}"
            )

    @staticmethod
    def _row_to_pending(row: sa.engine.Row) -> PendingClarification:
        return PendingClarification(
            id=UUID(row.id),
            tenant_id=UUID(row.tenant_id),
            jurisdiction=row.jurisdiction,
            user_id=row.user_id,
            originating_channel=row.originating_channel,
            originating_user_address=row.originating_user_address,
            originating_intake_id=UUID(row.originating_intake_id),
            proposed_intent=dict(row.proposed_intent),
            proposed_action_summary=row.proposed_action_summary,
            status=PendingClarificationStatus(row.status),
            created_at=row.created_at,
            expires_at=row.expires_at,
            resolved_at=row.resolved_at,
        )

    async def save(
        self,
        *,
        tenant_context: TenantContext,
        pending: PendingClarification,
    ) -> None:
        self._assert_bound(tenant_context)
        self._assert_entity_tenant(pending.tenant_id)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(pending_table).values(
                        id=str(pending.id),
                        tenant_id=str(pending.tenant_id),
                        jurisdiction=pending.jurisdiction,
                        user_id=pending.user_id,
                        originating_channel=pending.originating_channel,
                        originating_user_address=pending.originating_user_address,
                        originating_intake_id=str(
                            pending.originating_intake_id
                        ),
                        proposed_intent=pending.proposed_intent,
                        proposed_action_summary=pending.proposed_action_summary,
                        status=pending.status.value,
                        created_at=pending.created_at,
                        expires_at=pending.expires_at,
                        resolved_at=pending.resolved_at,
                    )
                )

    async def update_status(
        self,
        *,
        tenant_context: TenantContext,
        pending: PendingClarification,
    ) -> None:
        self._assert_bound(tenant_context)
        self._assert_entity_tenant(pending.tenant_id)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.update(pending_table)
                    .where(
                        sa.and_(
                            pending_table.c.id == str(pending.id),
                            pending_table.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                    .values(
                        status=pending.status.value,
                        resolved_at=pending.resolved_at,
                    )
                )

    async def get_by_id(
        self,
        *,
        tenant_context: TenantContext,
        pending_id: UUID,
    ) -> PendingClarification | None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            row = (
                await session.execute(
                    sa.select(pending_table).where(
                        sa.and_(
                            pending_table.c.id == str(pending_id),
                            pending_table.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                )
            ).one_or_none()
        return None if row is None else self._row_to_pending(row)

    async def get_active_for_user(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
    ) -> PendingClarification | None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            row = (
                await session.execute(
                    sa.select(pending_table).where(
                        sa.and_(
                            pending_table.c.tenant_id
                            == str(self._bound_tenant_id),
                            pending_table.c.user_id == user_id,
                            pending_table.c.status
                            == PendingClarificationStatus.PENDING.value,
                        )
                    )
                )
            ).one_or_none()
        return None if row is None else self._row_to_pending(row)


__all__ = ["PostgresPendingClarificationRepository"]
