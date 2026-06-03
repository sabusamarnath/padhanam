"""Postgres adapter for the email ConnectionRepository (D151).

Mirrors calendar's connection_repository with the ``history_id`` anchor in
place of the sync_token, bound-tenant-id defence-in-depth (D24).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel import TenantContext, TenantId

from contexts.email.adapters.outbound.postgres._tables import (
    email_connections as connections_table,
)
from contexts.email.domain.connection import Connection


class _SessionFactoryResolver(Protocol):
    async def __call__(self, tenant_id: TenantId) -> async_sessionmaker[AsyncSession]: ...


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
    """Email ConnectionRepository adapter (D151)."""

    def __init__(
        self, *, per_tenant_sessionmaker_resolver: _SessionFactoryResolver, bound_tenant_id: TenantId
    ) -> None:
        self._resolve = per_tenant_sessionmaker_resolver
        self._bound = bound_tenant_id

    def _assert_bound(self, tc: TenantContext) -> None:
        if str(tc.tenant_id) != str(self._bound):
            raise ValueError("email connection repo bound-tenant mismatch (D24/D32)")

    async def save_connection(self, *, tenant_context: TenantContext, connection: Connection) -> None:
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

    async def get_history_id(
        self, *, tenant_context: TenantContext, connection_id: UUID
    ) -> str | None:
        self._assert_bound(tenant_context)
        stmt = sa.select(connections_table.c.history_id).where(
            connections_table.c.tenant_id == str(self._bound),
            connections_table.c.id == str(connection_id),
        )
        sm = await self._resolve(self._bound)
        async with sm() as s:
            return (await s.execute(stmt)).scalar_one_or_none()

    async def set_history_id(
        self, *, tenant_context: TenantContext, connection_id: UUID, history_id: str | None
    ) -> None:
        self._assert_bound(tenant_context)
        stmt = (
            sa.update(connections_table)
            .where(
                connections_table.c.tenant_id == str(self._bound),
                connections_table.c.id == str(connection_id),
            )
            .values(history_id=history_id, updated_at=datetime.now(timezone.utc))
        )
        sm = await self._resolve(self._bound)
        async with sm() as s:
            async with s.begin():
                await s.execute(stmt)


__all__ = ["PostgresConnectionRepository"]
