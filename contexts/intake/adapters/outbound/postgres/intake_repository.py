"""Postgres adapter for IntakeRepository (D127, S44b).

Implements ``IntakeRepository`` against per-tenant Postgres data
planes per D32. SQLAlchemy 2.0 Core, manual entity-to-row
conversion, no ORM, bound-tenant-id defence-in-depth at
construction — mirroring the portfolio adapter shape.

The ``payload`` JSONB column carries the serialised IntakePayload
variant; ``intake_source`` discriminates which variant. At S44b the
single MANUAL_ENTRY / ManualEntryPayload variant; the
``_payload_from_row`` dispatch widens when P14 lands the second
variant.

Cursor pagination on ``(created_at DESC, id DESC)`` with tuple
comparison; the cursor ``id`` literal is cast to ``pg.UUID``
explicitly per the S33 finding.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel import ActorReference, TenantContext, TenantId

from contexts.intake.adapters.outbound.postgres._tables import (
    intakes as intakes_table,
)
from contexts.intake.domain import (
    IntakePayload,
    IntakeRecord,
    IntakeSource,
    ManualEntryPayload,
)
from contexts.intake.domain.query_filters import (
    IntakeListCursor,
    IntakeListFilters,
)
from contexts.intake.ports.intake_repository import IntakeListPage


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


def _payload_to_json(payload: IntakePayload) -> dict[str, Any]:
    """Serialise an IntakePayload variant to a JSONB-ready dict."""
    return {
        "raw_text": payload.raw_text,
        "intent_hint": payload.intent_hint,
        "linked_case_ids": [str(c) for c in payload.linked_case_ids],
    }


def _payload_from_row(
    intake_source: IntakeSource, raw: dict[str, Any]
) -> IntakePayload:
    """Reconstruct an IntakePayload variant from a JSONB row value.

    Dispatches on ``intake_source``; at S44b the single
    MANUAL_ENTRY → ManualEntryPayload mapping.
    """
    if intake_source is IntakeSource.MANUAL_ENTRY:
        return ManualEntryPayload(
            raw_text=raw["raw_text"],
            intent_hint=raw.get("intent_hint"),
            linked_case_ids=tuple(
                UUID(c) for c in raw.get("linked_case_ids", [])
            ),
        )
    raise ValueError(f"unknown intake_source {intake_source!r}")


class PostgresIntakeRepository:
    """Adapter implementation of ``IntakeRepository`` (D127)."""

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
                f"IntakeRecord.tenant_id={entity_tenant_id!r} does not match "
                f"adapter's bound tenant {self._bound_tenant_id!r}"
            )

    @staticmethod
    def _row_to_intake(row: sa.engine.Row) -> IntakeRecord:
        intake_source = IntakeSource(row.intake_source)
        return IntakeRecord(
            id=UUID(row.id),
            tenant_id=UUID(row.tenant_id),
            jurisdiction=row.jurisdiction,
            intake_source=intake_source,
            payload=_payload_from_row(intake_source, row.payload),
            authored_by=ActorReference(user_id=row.authored_by_user_id),
            created_at=row.created_at,
        )

    async def save(
        self, *, tenant_context: TenantContext, intake: IntakeRecord
    ) -> None:
        self._assert_bound(tenant_context)
        self._assert_entity_tenant(intake.tenant_id)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(intakes_table).values(
                        id=str(intake.id),
                        tenant_id=str(intake.tenant_id),
                        jurisdiction=intake.jurisdiction,
                        intake_source=intake.intake_source.value,
                        payload=_payload_to_json(intake.payload),
                        authored_by_user_id=intake.authored_by.user_id,
                        created_at=intake.created_at,
                    )
                )

    async def get_by_id(
        self, *, tenant_context: TenantContext, intake_id: UUID
    ) -> IntakeRecord | None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            row = (
                await session.execute(
                    sa.select(intakes_table).where(
                        sa.and_(
                            intakes_table.c.id == str(intake_id),
                            intakes_table.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                )
            ).one_or_none()
        return None if row is None else self._row_to_intake(row)

    async def list_for_tenant(
        self,
        *,
        tenant_context: TenantContext,
        filters: IntakeListFilters | None,
        cursor: IntakeListCursor | None,
        page_size: int,
    ) -> IntakeListPage:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            stmt = sa.select(intakes_table).where(
                intakes_table.c.tenant_id == str(self._bound_tenant_id)
            )
            if filters is not None and filters.intake_sources is not None:
                stmt = stmt.where(
                    intakes_table.c.intake_source.in_(
                        [s.value for s in filters.intake_sources]
                    )
                )
            if cursor is not None:
                stmt = stmt.where(
                    sa.tuple_(
                        intakes_table.c.created_at, intakes_table.c.id
                    )
                    < sa.tuple_(
                        sa.literal(cursor.created_at),
                        sa.cast(sa.literal(str(cursor.id)), pg.UUID),
                    )
                )
            stmt = stmt.order_by(
                intakes_table.c.created_at.desc(),
                intakes_table.c.id.desc(),
            ).limit(page_size + 1)
            rows = (await session.execute(stmt)).all()

        next_cursor: IntakeListCursor | None = None
        if len(rows) > page_size:
            page_rows = rows[:page_size]
            last = page_rows[-1]
            next_cursor = IntakeListCursor(
                created_at=last.created_at,
                id=UUID(last.id),
                page_size=page_size,
            )
        else:
            page_rows = rows
        return IntakeListPage(
            intakes=tuple(self._row_to_intake(r) for r in page_rows),
            next_cursor=next_cursor,
        )


__all__ = ["PostgresIntakeRepository"]
