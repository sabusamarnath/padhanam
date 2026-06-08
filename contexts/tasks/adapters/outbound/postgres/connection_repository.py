"""Postgres adapter for the tasks ConnectionRepository (D167).

Mirrors calendar/email's connection repository with bound-tenant-id
defence-in-depth (D24). No sync-token/history-id anchor — Google Tasks re-pulls
fully each refresh.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel import TenantContext, TenantId

from contexts.tasks.adapters.outbound.postgres._tables import (
    task_connections as connections_table,
)
from contexts.tasks.domain.connection import Connection


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
    """Tasks ConnectionRepository adapter (D167)."""

    def __init__(
        self,
        *,
        per_tenant_sessionmaker_resolver: _SessionFactoryResolver,
        bound_tenant_id: TenantId,
    ) -> None:
        self._resolve = per_tenant_sessionmaker_resolver
        self._bound = bound_tenant_id

    def _assert_bound(self, tc: TenantContext) -> None:
        if str(tc.tenant_id) != str(self._bound):
            raise ValueError(
                "tasks connection repo bound-tenant mismatch (D24/D32)"
            )

    async def save_connection(
        self, *, tenant_context: TenantContext, connection: Connection
    ) -> None:
        self._assert_bound(tenant_context)
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
        sm = await self._resolve(self._bound)
        async with sm() as s:
            async with s.begin():
                await s.execute(stmt)

    async def get_connection(
        self, *, tenant_context: TenantContext, connection_id: UUID
    ) -> Connection | None:
        self._assert_bound(tenant_context)
        stmt = sa.select(connections_table).where(
            connections_table.c.tenant_id == str(self._bound),
            connections_table.c.id == str(connection_id),
        )
        sm = await self._resolve(self._bound)
        async with sm() as s:
            row = (await s.execute(stmt)).mappings().first()
        return _row_to_connection(dict(row)) if row else None


__all__ = ["PostgresConnectionRepository"]
