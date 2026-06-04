"""Postgres adapter for DayRepository (D157).

Per-tenant Postgres data planes, SQLAlchemy 2.0 Core, tenant-id bound at
construction. The minimal Day concept: only ``position`` and ``done``
persist, keyed ``(tenant_id, user_id, day_date, item_kind, item_id)``.
Upserts use ``INSERT ... ON CONFLICT DO UPDATE`` so reordering does not
clobber a done mark and vice versa.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.daily_driver.adapters.outbound.postgres._tables import (
    day_item_states as states_table,
)
from contexts.daily_driver.domain.day import DayItemState
from contexts.daily_driver.domain.today_item import ItemKind
from shared_kernel import TenantContext, TenantId

_CONFLICT_COLUMNS = (
    "tenant_id",
    "user_id",
    "day_date",
    "item_kind",
    "item_id",
)


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresDayRepository:
    """Adapter implementation of ``DayRepository`` (D157)."""

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

    async def get_states(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        day_date: date,
    ) -> tuple[DayItemState, ...]:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            rows = (
                await session.execute(
                    sa.select(states_table).where(
                        sa.and_(
                            states_table.c.tenant_id
                            == str(self._bound_tenant_id),
                            states_table.c.user_id == user_id,
                            states_table.c.day_date == day_date,
                        )
                    )
                )
            ).all()
        return tuple(
            DayItemState(
                kind=ItemKind(row.item_kind),
                item_id=UUID(row.item_id),
                position=row.position,
                done=row.done,
            )
            for row in rows
        )

    async def set_positions(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        day_date: date,
        ordered_keys: tuple[tuple[ItemKind, UUID], ...],
    ) -> None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                for position, (kind, item_id) in enumerate(ordered_keys):
                    stmt = pg.insert(states_table).values(
                        id=str(uuid4()),
                        tenant_id=str(self._bound_tenant_id),
                        jurisdiction=tenant_context.jurisdiction,
                        user_id=user_id,
                        day_date=day_date,
                        item_kind=kind.value,
                        item_id=str(item_id),
                        position=position,
                        done=False,
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=_CONFLICT_COLUMNS,
                        set_={
                            "position": position,
                            "updated_at": sa.func.now(),
                        },
                    )
                    await session.execute(stmt)

    async def set_done(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        day_date: date,
        kind: ItemKind,
        item_id: UUID,
        done: bool,
    ) -> None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                stmt = pg.insert(states_table).values(
                    id=str(uuid4()),
                    tenant_id=str(self._bound_tenant_id),
                    jurisdiction=tenant_context.jurisdiction,
                    user_id=user_id,
                    day_date=day_date,
                    item_kind=kind.value,
                    item_id=str(item_id),
                    position=None,
                    done=done,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=_CONFLICT_COLUMNS,
                    set_={"done": done, "updated_at": sa.func.now()},
                )
                await session.execute(stmt)


__all__ = ["PostgresDayRepository"]
