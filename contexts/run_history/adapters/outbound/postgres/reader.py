"""Postgres adapter for the run-history read port (D97, S33).

Implements ``RunHistoryReader`` against per-tenant Postgres data
planes per D32 / D34 / D36. SQLAlchemy 2.0 Core (Table + select via
AsyncSession), manual row-to-record conversion; no DeclarativeBase,
no ORM. Mirrors the writer adapter's shape at
``contexts/run_history/adapters/outbound/postgres/repository.py``.

Per-tenant session-factory resolution flows through the same
``per_tenant_sessionmaker_resolver`` callable the writer uses;
the wiring layer at ``apps/cli/_cross_context.py``
(``RunHistoryReaderAdapter``, S33 commit 4) supplies the resolver
bound to a runtime ``tenant_context`` at call time. The reader
adopts the same bound-tenant-id defence-in-depth check the writer
uses so a mis-routed read cannot serve another tenant's data.

``get_run`` issues three queries (run row, chunk citations, entity
citations) rather than a single LEFT JOIN. The reasoning: Phase 1
citation cardinality is single-digit per run so the round-trip
cost is bounded, and three queries produce row sets without the
cartesian-product blowup of LEFT JOIN-of-LEFT-JOIN over the two
citation tables. The structural clarity at the assembly layer
(one query per record type) outweighs the round-trip cost at
Phase 1 cardinality. Phase 2 evidence revisits if a real consumer
surfaces a latency case.

``list_runs_with_filters`` issues one query against ``runs`` only.
Citations are not loaded at list-view altitude per D97's bounded-
cardinality argument; the returned ``RunRecord`` instances carry
empty citation tuples.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.run_history.adapters.outbound.postgres.repository import (
    run_chunk_citations,
    run_entity_citations,
    runs,
)
from contexts.run_history.domain.citation_records import (
    ChunkCitationRecord,
    EntityCitationRecord,
)
from contexts.run_history.domain.query_filters import (
    PAGE_SIZE_CEILING,
    RunListCursor,
    RunListFilters,
)
from contexts.run_history.domain.run_record import RunRecord
from contexts.run_history.ports.reader import RunListPage
from shared_kernel import TenantContext, TenantId


class _SessionFactoryResolver(Protocol):
    """Same shape as the writer adapter's resolver — given a
    ``TenantId``, return the per-tenant ``async_sessionmaker``."""

    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresRunHistoryReader:
    """Adapter implementation of ``RunHistoryReader`` (D97).

    Constructor mirrors ``PostgresRunHistoryAdapter`` (the writer):
    takes a per-tenant session-factory resolver and a bound tenant
    id. The bound tenant id is the defence-in-depth anchor: every
    read call validates the incoming ``TenantContext.tenant_id``
    against the bound tenant before any session opens.
    """

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

    async def get_run(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
    ) -> RunRecord | None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            run_row = (
                await session.execute(
                    sa.select(runs).where(
                        sa.and_(
                            runs.c.id == str(run_id),
                            runs.c.tenant_id == str(self._bound_tenant_id),
                        )
                    )
                )
            ).first()
            if run_row is None:
                return None

            chunk_rows = (
                await session.execute(
                    sa.select(run_chunk_citations)
                    .where(
                        sa.and_(
                            run_chunk_citations.c.run_id == str(run_id),
                            run_chunk_citations.c.tenant_id == str(self._bound_tenant_id),
                        )
                    )
                    .order_by(run_chunk_citations.c.id.asc())
                )
            ).all()
            entity_rows = (
                await session.execute(
                    sa.select(run_entity_citations)
                    .where(
                        sa.and_(
                            run_entity_citations.c.run_id == str(run_id),
                            run_entity_citations.c.tenant_id == str(self._bound_tenant_id),
                        )
                    )
                    .order_by(run_entity_citations.c.id.asc())
                )
            ).all()

        return _build_run_record(
            run_row=run_row,
            chunk_rows=chunk_rows,
            entity_rows=entity_rows,
        )

    async def list_runs_with_filters(
        self,
        *,
        tenant_context: TenantContext,
        filters: RunListFilters,
        cursor: RunListCursor | None,
    ) -> RunListPage:
        self._assert_bound(tenant_context)
        page_size = cursor.page_size if cursor is not None else PAGE_SIZE_CEILING

        clauses = [runs.c.tenant_id == str(self._bound_tenant_id)]
        if filters.agent_template_ids is not None:
            clauses.append(
                runs.c.agent_template_id.in_(
                    [str(a) for a in filters.agent_template_ids]
                )
            )
        if filters.agent_template_versions is not None:
            clauses.append(
                runs.c.agent_template_version.in_(filters.agent_template_versions)
            )
        if filters.started_at_range is not None:
            lower, upper = filters.started_at_range
            clauses.append(runs.c.started_at >= lower)
            clauses.append(runs.c.started_at < upper)
        if filters.termination_reasons is not None:
            clauses.append(
                runs.c.termination_reason.in_(filters.termination_reasons)
            )
        if cursor is not None:
            # Row-value tuple comparison: (started_at, id) < (cursor_started_at, cursor_id)
            # paginates stably under the (started_at DESC, id DESC) sort.
            clauses.append(
                sa.tuple_(runs.c.started_at, runs.c.id)
                < sa.tuple_(cursor.started_at, str(cursor.id))
            )

        query = (
            sa.select(runs)
            .where(sa.and_(*clauses))
            .order_by(runs.c.started_at.desc(), runs.c.id.desc())
            .limit(page_size + 1)
        )

        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            rows = (await session.execute(query)).all()

        has_next = len(rows) > page_size
        page_rows = rows[:page_size]
        records = tuple(
            _build_run_record(run_row=r, chunk_rows=(), entity_rows=())
            for r in page_rows
        )
        if has_next and page_rows:
            last = page_rows[-1]
            next_cursor: RunListCursor | None = RunListCursor(
                started_at=last.started_at,
                id=UUID(last.id) if isinstance(last.id, str) else last.id,
                page_size=page_size,
            )
        else:
            next_cursor = None

        return RunListPage(runs=records, next_cursor=next_cursor)


def _coerce_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _coerce_optional_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    return _coerce_uuid(value)


def _build_run_record(
    *,
    run_row: sa.engine.Row,
    chunk_rows: list[sa.engine.Row] | tuple,
    entity_rows: list[sa.engine.Row] | tuple,
) -> RunRecord:
    """Map a runs row plus its citation rows into a RunRecord."""
    chunk_citations = tuple(
        ChunkCitationRecord(
            id=_coerce_uuid(row.id),
            run_id=_coerce_uuid(row.run_id),
            chunk_id=_coerce_optional_uuid(row.chunk_id),
            tenant_id=row.tenant_id,
            jurisdiction=row.jurisdiction,
            chunk_excerpt=row.chunk_excerpt,
            source_snapshot=row.source_snapshot or {},
        )
        for row in chunk_rows
    )
    entity_citations = tuple(
        EntityCitationRecord(
            id=_coerce_uuid(row.id),
            run_id=_coerce_uuid(row.run_id),
            entity_tenant_id=row.entity_tenant_id,
            entity_name=row.entity_name,
            entity_type=row.entity_type,
            tenant_id=row.tenant_id,
            source_chunk_ids=tuple(
                _coerce_uuid(cid) for cid in (row.source_chunk_ids or [])
            ),
        )
        for row in entity_rows
    )
    total_cost = run_row.total_cost_usd
    if not isinstance(total_cost, Decimal):
        total_cost = Decimal(str(total_cost))
    return RunRecord(
        id=_coerce_uuid(run_row.id),
        tenant_id=run_row.tenant_id,
        jurisdiction=run_row.jurisdiction,
        agent_template_id=_coerce_uuid(run_row.agent_template_id),
        agent_template_version=run_row.agent_template_version,
        input_message=run_row.input_message,
        output_content=run_row.output_content,
        started_at=run_row.started_at,
        completed_at=run_row.completed_at,
        termination_reason=run_row.termination_reason,
        iteration_count=run_row.iteration_count,
        total_cost_usd=total_cost,
        trace_id=run_row.trace_id,
        audit_start_hash=run_row.audit_start_hash,
        audit_end_hash=run_row.audit_end_hash,
        created_at=run_row.created_at,
        chunk_citations=chunk_citations,
        entity_citations=entity_citations,
    )


__all__ = ["PostgresRunHistoryReader"]
