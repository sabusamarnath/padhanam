"""Postgres adapter for MessageRepository (D129).

Implements ``MessageRepository`` against per-tenant Postgres data
planes per D32. SQLAlchemy 2.0 Core, manual entity-to-row
conversion, no ORM, bound-tenant-id defence-in-depth at
construction — mirroring the intake adapter shape.

Cursor pagination on ``(created_at DESC, id DESC)`` with tuple
comparison; the cursor ``id`` literal is cast to ``pg.UUID``
explicitly per the S33 finding.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.messaging.adapters.outbound.postgres._tables import (
    messages as messages_table,
)
from contexts.messaging.domain import (
    Message,
    MessageChannel,
    MessageDirection,
    MessageStatus,
)
from contexts.messaging.domain.query_filters import (
    MessageListCursor,
    MessageListFilters,
)
from contexts.messaging.ports.message_repository import MessageListPage
from shared_kernel import TenantContext, TenantId


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresMessageRepository:
    """Adapter implementation of ``MessageRepository`` (D129)."""

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
                f"Message.tenant_id={entity_tenant_id!r} does not match "
                f"adapter's bound tenant {self._bound_tenant_id!r}"
            )

    @staticmethod
    def _row_to_message(row: sa.engine.Row) -> Message:
        return Message(
            id=UUID(row.id),
            tenant_id=UUID(row.tenant_id),
            jurisdiction=row.jurisdiction,
            direction=MessageDirection(row.direction),
            channel=MessageChannel(row.channel),
            body=row.body,
            from_address=row.from_address,
            to_address=row.to_address,
            status=MessageStatus(row.status),
            actor_id=row.actor_id,
            created_at=row.created_at,
            external_id=row.external_id,
            intake_id=None if row.intake_id is None else UUID(row.intake_id),
            cell_payload=(
                None if row.cell_payload is None else dict(row.cell_payload)
            ),
        )

    async def save(
        self, *, tenant_context: TenantContext, message: Message
    ) -> None:
        self._assert_bound(tenant_context)
        self._assert_entity_tenant(message.tenant_id)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(messages_table).values(
                        id=str(message.id),
                        tenant_id=str(message.tenant_id),
                        jurisdiction=message.jurisdiction,
                        direction=message.direction.value,
                        channel=message.channel.value,
                        body=message.body,
                        from_address=message.from_address,
                        to_address=message.to_address,
                        status=message.status.value,
                        external_id=message.external_id,
                        intake_id=(
                            None
                            if message.intake_id is None
                            else str(message.intake_id)
                        ),
                        actor_id=message.actor_id,
                        created_at=message.created_at,
                        cell_payload=message.cell_payload,
                    )
                )

    async def get_by_id(
        self, *, tenant_context: TenantContext, message_id: UUID
    ) -> Message | None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            row = (
                await session.execute(
                    sa.select(messages_table).where(
                        sa.and_(
                            messages_table.c.id == str(message_id),
                            messages_table.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                )
            ).one_or_none()
        return None if row is None else self._row_to_message(row)

    async def list_for_tenant(
        self,
        *,
        tenant_context: TenantContext,
        filters: MessageListFilters | None,
        cursor: MessageListCursor | None,
        page_size: int,
    ) -> MessageListPage:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            stmt = sa.select(messages_table).where(
                messages_table.c.tenant_id == str(self._bound_tenant_id)
            )
            if filters is not None and filters.directions is not None:
                stmt = stmt.where(
                    messages_table.c.direction.in_(
                        [d.value for d in filters.directions]
                    )
                )
            if filters is not None and filters.channels is not None:
                stmt = stmt.where(
                    messages_table.c.channel.in_(
                        [c.value for c in filters.channels]
                    )
                )
            if cursor is not None:
                stmt = stmt.where(
                    sa.tuple_(
                        messages_table.c.created_at, messages_table.c.id
                    )
                    < sa.tuple_(
                        sa.literal(cursor.created_at),
                        sa.cast(sa.literal(str(cursor.id)), pg.UUID),
                    )
                )
            stmt = stmt.order_by(
                messages_table.c.created_at.desc(),
                messages_table.c.id.desc(),
            ).limit(page_size + 1)
            rows = (await session.execute(stmt)).all()

        next_cursor: MessageListCursor | None = None
        if len(rows) > page_size:
            page_rows = rows[:page_size]
            last = page_rows[-1]
            next_cursor = MessageListCursor(
                created_at=last.created_at,
                id=UUID(last.id),
                page_size=page_size,
            )
        else:
            page_rows = rows
        return MessageListPage(
            messages=tuple(self._row_to_message(r) for r in page_rows),
            next_cursor=next_cursor,
        )


__all__ = ["PostgresMessageRepository"]
