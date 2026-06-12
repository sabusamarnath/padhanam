"""Postgres adapter for MatcherPolicyRepository (D186/S91b).

Upserts the tenant's active policy (ON CONFLICT on the tenant_id primary key),
mirroring the per-tenant, bound-tenant, SQLAlchemy-2.0-Core pattern. Idempotent —
re-applying the same policy is a no-op-shaped upsert.
"""

from __future__ import annotations

from typing import Protocol

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel import TenantContext, TenantId

from contexts.matcher_policy.adapters.outbound.postgres._tables import (
    matcher_policies,
)
from contexts.matcher_policy.domain import MatcherPolicy


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresMatcherPolicyRepository:
    """Adapter implementation of ``MatcherPolicyRepository`` (D186)."""

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

    async def set_policy(
        self, *, tenant_context: TenantContext, policy: MatcherPolicy
    ) -> None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        stmt = pg_insert(matcher_policies).values(
            tenant_id=str(self._bound_tenant_id),
            suppress_single_signal=policy.suppress_single_signal,
            updated_at=sa.func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[matcher_policies.c.tenant_id],
            set_={
                "suppress_single_signal": policy.suppress_single_signal,
                "updated_at": sa.func.now(),
            },
        )
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(stmt)


__all__ = ["PostgresMatcherPolicyRepository"]
