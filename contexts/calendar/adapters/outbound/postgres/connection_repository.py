"""Postgres adapter for ConnectionRepository (D148).

Persists the tenant's calendar Connection (identity: provider plus the
opaque provider references) and its per-connection sync-token state, with
bound-tenant-id defence-in-depth (D24). The Connection value object stays
identity-only; the sync token lives in a dedicated column accessed through
get/set methods.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel import TenantContext, TenantId

from contexts.calendar.adapters.outbound.postgres._tables import (
    connections as connections_table,
)
from contexts.calendar.domain.connection import Connection


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


def _row_to_connection(row: dict[str, Any]) -> Connection:
    return Connection(
        id=UUID(str(row["id"])),
        tenant_id=UUID(str(row["tenant_id"])),
        jurisdiction=row["jurisdiction"],
        provider=row["provider"],
        provider_config_key=row["provider_config_key"],
        provider_connection_ref=row["provider_connection_ref"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresConnectionRepository:
    """Adapter implementing ConnectionRepository (D148)."""

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

    async def save_connection(
        self, *, tenant_context: TenantContext, connection: Connection
    ) -> None:
        self._assert_bound(tenant_context)
        if str(connection.tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"Connection.tenant_id={connection.tenant_id!r} does not "
                f"match adapter's bound tenant {self._bound_tenant_id!r}"
            )
        values = {
            "id": str(connection.id),
            "tenant_id": str(connection.tenant_id),
            "jurisdiction": connection.jurisdiction,
            "provider": connection.provider,
            "provider_config_key": connection.provider_config_key,
            "provider_connection_ref": connection.provider_connection_ref,
            "created_at": connection.created_at,
            "updated_at": connection.updated_at,
        }
        stmt = pg_insert(connections_table).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "provider", "provider_config_key"],
            set_={
                "provider_connection_ref": stmt.excluded.provider_connection_ref,
                "jurisdiction": stmt.excluded.jurisdiction,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(stmt)

    async def get_connection(
        self, *, tenant_context: TenantContext, connection_id: UUID
    ) -> Connection | None:
        self._assert_bound(tenant_context)
        stmt = sa.select(connections_table).where(
            connections_table.c.tenant_id == str(self._bound_tenant_id),
            connections_table.c.id == str(connection_id),
        )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            result = await session.execute(stmt)
            row = result.mappings().first()
        return _row_to_connection(dict(row)) if row is not None else None

    async def get_sync_token(
        self, *, tenant_context: TenantContext, connection_id: UUID
    ) -> str | None:
        self._assert_bound(tenant_context)
        stmt = sa.select(connections_table.c.sync_token).where(
            connections_table.c.tenant_id == str(self._bound_tenant_id),
            connections_table.c.id == str(connection_id),
        )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            result = await session.execute(stmt)
            value = result.scalar_one_or_none()
        return value

    async def set_sync_token(
        self,
        *,
        tenant_context: TenantContext,
        connection_id: UUID,
        sync_token: str | None,
    ) -> None:
        self._assert_bound(tenant_context)
        stmt = (
            sa.update(connections_table)
            .where(
                connections_table.c.tenant_id == str(self._bound_tenant_id),
                connections_table.c.id == str(connection_id),
            )
            .values(
                sync_token=sync_token,
                updated_at=datetime.now(timezone.utc),
            )
        )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(stmt)


__all__ = ["PostgresConnectionRepository"]
