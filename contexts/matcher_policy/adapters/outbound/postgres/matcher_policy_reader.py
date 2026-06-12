"""Postgres adapter for MatcherPolicyReader (D186/S91b).

Reads the tenant's active policy row; returns ``MatcherPolicy.inactive()`` when
there is none (flag off — the S90 baseline behaviour). Bound-tenant,
SQLAlchemy-2.0-Core, no ORM.
"""

from __future__ import annotations

from typing import Protocol

import sqlalchemy as sa
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


class PostgresMatcherPolicyReader:
    """Adapter implementation of ``MatcherPolicyReader`` (D186)."""

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

    async def get_policy(
        self, *, tenant_context: TenantContext
    ) -> MatcherPolicy:
        self._assert_bound(tenant_context)
        t = matcher_policies
        stmt = sa.select(t.c.suppress_single_signal).where(
            t.c.tenant_id == str(self._bound_tenant_id)
        )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            result = await session.execute(stmt)
            row = result.first()
        if row is None:
            return MatcherPolicy.inactive()
        return MatcherPolicy(suppress_single_signal=bool(row.suppress_single_signal))


__all__ = ["PostgresMatcherPolicyReader"]
