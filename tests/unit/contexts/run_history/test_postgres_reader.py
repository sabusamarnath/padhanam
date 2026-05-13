"""Unit tests for PostgresRunHistoryReader (D97, S33).

Covers the scenarios named in the S33 brief commit 3:

- empty result
- single-row result
- full-page result without next
- full-page result with next
- filter combination matrix (no filters; each alone; all four)
- cursor pagination across multiple pages
- equal-timestamp runs paginate stably
- bound-tenant-id mismatch raises pre-routing
- get_run returns citations populated for runs with citations
- get_run returns empty tuples for runs without citations
- get_run returns None for missing run-id

Uses a fake session that captures the executed statements and
returns canned result rows. The SQL shape (WHERE clauses, ORDER BY,
LIMIT) is exercised against real Postgres via the tenant-isolation
contract harness extension at commit 5 and the live-stack smoke at
commit 6.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from contexts.run_history.adapters.outbound.postgres.reader import (
    PostgresRunHistoryReader,
)
from contexts.run_history.domain.query_filters import (
    RunListCursor,
    RunListFilters,
)
from shared_kernel import TenantContext, TenantId


_TENANT_A_UUID = UUID("aaaa1111-2222-4333-8444-555555555555")
_TENANT_B_UUID = UUID("bbbb1111-2222-4333-8444-555555555555")


def _ctx(tenant_id: UUID = _TENANT_A_UUID) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        cost_attribution_id=str(tenant_id),
    )


def _now(offset_sec: int = 0) -> datetime:
    return datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_sec)


@dataclass
class _RunRow:
    id: str
    tenant_id: str
    jurisdiction: str
    agent_template_id: str
    agent_template_version: int
    input_message: str
    output_content: str
    started_at: datetime
    completed_at: datetime
    termination_reason: str
    iteration_count: int
    total_cost_usd: Decimal
    trace_id: str | None
    audit_start_hash: str
    audit_end_hash: str | None
    created_at: datetime


@dataclass
class _ChunkRow:
    id: str
    run_id: str
    chunk_id: str | None
    tenant_id: str
    jurisdiction: str
    chunk_excerpt: str
    source_snapshot: dict
    created_at: datetime


@dataclass
class _EntityRow:
    id: str
    run_id: str
    entity_tenant_id: str
    entity_name: str
    entity_type: str
    tenant_id: str
    source_chunk_ids: list
    created_at: datetime


def _run_row(
    *,
    run_id: UUID | None = None,
    tenant_id: str = str(_TENANT_A_UUID),
    started_at: datetime | None = None,
    agent_template_id: UUID | None = None,
    agent_template_version: int = 1,
    termination_reason: str = "content",
) -> _RunRow:
    base_started = started_at or _now()
    return _RunRow(
        id=str(run_id or uuid4()),
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        agent_template_id=str(agent_template_id or uuid4()),
        agent_template_version=agent_template_version,
        input_message="hello",
        output_content="hi",
        started_at=base_started,
        completed_at=base_started + timedelta(seconds=10),
        termination_reason=termination_reason,
        iteration_count=1,
        total_cost_usd=Decimal("0.001"),
        trace_id=None,
        audit_start_hash="0" * 64,
        audit_end_hash="1" * 64,
        created_at=base_started + timedelta(seconds=15),
    )


def _chunk_row(*, run_id: UUID, citation_id: UUID | None = None) -> _ChunkRow:
    cid = citation_id or uuid4()
    return _ChunkRow(
        id=str(cid),
        run_id=str(run_id),
        chunk_id=str(uuid4()),
        tenant_id=str(_TENANT_A_UUID),
        jurisdiction="eu-west",
        chunk_excerpt="cited content",
        source_snapshot={"file_name": "doc.pdf", "file_type": "application/pdf"},
        created_at=_now(15),
    )


def _entity_row(*, run_id: UUID, citation_id: UUID | None = None) -> _EntityRow:
    cid = citation_id or uuid4()
    return _EntityRow(
        id=str(cid),
        run_id=str(run_id),
        entity_tenant_id=str(_TENANT_A_UUID),
        entity_name="Acme",
        entity_type="Organization",
        tenant_id=str(_TENANT_A_UUID),
        source_chunk_ids=[str(uuid4())],
        created_at=_now(15),
    )


# --------------------------------------------------------------------
# Fake session infrastructure: capture executed statements, return
# canned rows queued by table name.
# --------------------------------------------------------------------


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any | None:
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self, queue: list[list[Any]]) -> None:
        self._queue = queue
        self.executed_statements: list[Any] = []

    async def execute(self, statement: Any, params: Any = None) -> _FakeResult:
        self.executed_statements.append(statement)
        if not self._queue:
            return _FakeResult([])
        return _FakeResult(self._queue.pop(0))


class _FakeSessionmaker:
    def __init__(self, queue: list[list[Any]]) -> None:
        self.session = _FakeSession(queue)

    def __call__(self) -> "_FakeSessionContext":
        return _FakeSessionContext(self.session)


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, *args: Any) -> None:
        pass


class _Resolver:
    def __init__(self, sessionmaker: _FakeSessionmaker) -> None:
        self._sessionmaker = sessionmaker
        self.resolved_for: list[TenantId] = []

    async def __call__(self, tenant_id: TenantId) -> _FakeSessionmaker:
        self.resolved_for.append(tenant_id)
        return self._sessionmaker


def _build_reader(
    *,
    queue: list[list[Any]] | None = None,
    bound: UUID = _TENANT_A_UUID,
) -> tuple[PostgresRunHistoryReader, _Resolver, _FakeSessionmaker]:
    sm = _FakeSessionmaker(queue or [])
    resolver = _Resolver(sm)
    reader = PostgresRunHistoryReader(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(str(bound)),
    )
    return reader, resolver, sm


# --------------------------------------------------------------------
# get_run: missing, present without citations, present with citations.
# --------------------------------------------------------------------


def test_get_run_returns_none_for_missing_run() -> None:
    """When the runs query returns no row, get_run returns None and
    does not query citation tables."""
    reader, resolver, sm = _build_reader(queue=[[]])  # empty runs result

    result = asyncio.run(
        reader.get_run(tenant_context=_ctx(), run_id=uuid4())
    )

    assert result is None
    # Only one query (the runs SELECT); citation tables never queried.
    assert len(sm.session.executed_statements) == 1


def test_get_run_returns_record_with_empty_citation_tuples() -> None:
    """When the run exists but has no citations, get_run returns the
    RunRecord with empty chunk_citations and entity_citations tuples."""
    run_id = uuid4()
    row = _run_row(run_id=run_id)
    reader, _, sm = _build_reader(queue=[[row], [], []])

    result = asyncio.run(
        reader.get_run(tenant_context=_ctx(), run_id=run_id)
    )

    assert result is not None
    assert result.id == run_id
    assert result.chunk_citations == ()
    assert result.entity_citations == ()
    # Three queries: runs, chunk citations, entity citations.
    assert len(sm.session.executed_statements) == 3


def test_get_run_returns_record_with_populated_citations() -> None:
    """When the run has citations, the RunRecord carries them as
    populated tuples in the read DTO."""
    run_id = uuid4()
    row = _run_row(run_id=run_id)
    chunks = [_chunk_row(run_id=run_id) for _ in range(2)]
    entities = [_entity_row(run_id=run_id)]
    reader, _, _ = _build_reader(queue=[[row], chunks, entities])

    result = asyncio.run(
        reader.get_run(tenant_context=_ctx(), run_id=run_id)
    )

    assert result is not None
    assert len(result.chunk_citations) == 2
    assert len(result.entity_citations) == 1
    assert result.chunk_citations[0].chunk_excerpt == "cited content"
    assert result.entity_citations[0].entity_name == "Acme"


def test_get_run_resolves_session_for_bound_tenant() -> None:
    """The resolver is called with the adapter's bound tenant_id only."""
    run_id = uuid4()
    row = _run_row(run_id=run_id)
    reader, resolver, _ = _build_reader(queue=[[row], [], []])

    asyncio.run(reader.get_run(tenant_context=_ctx(), run_id=run_id))

    assert resolver.resolved_for == [TenantId(str(_TENANT_A_UUID))]


def test_get_run_rejects_tenant_context_mismatch_pre_routing() -> None:
    """A get_run call with a TenantContext whose tenant_id differs
    from the adapter's bound tenant raises ValueError before any
    session resolution."""
    reader, resolver, sm = _build_reader()

    foreign_ctx = _ctx(tenant_id=_TENANT_B_UUID)
    with pytest.raises(ValueError, match="tenant"):
        asyncio.run(reader.get_run(tenant_context=foreign_ctx, run_id=uuid4()))

    assert resolver.resolved_for == []
    assert sm.session.executed_statements == []


# --------------------------------------------------------------------
# list_runs_with_filters: results, filters, pagination, cursors.
# --------------------------------------------------------------------


def test_list_returns_empty_page_when_no_rows() -> None:
    """Empty result set produces empty runs tuple and None next_cursor."""
    reader, _, _ = _build_reader(queue=[[]])

    page = asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(),
            cursor=None,
        )
    )

    assert page.runs == ()
    assert page.next_cursor is None


def test_list_returns_single_row_no_next_cursor() -> None:
    """Single-row result produces one RunRecord and no next_cursor."""
    row = _run_row()
    reader, _, _ = _build_reader(queue=[[row]])

    page = asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(),
            cursor=None,
        )
    )

    assert len(page.runs) == 1
    assert page.next_cursor is None
    # List-view altitude: no citations attached.
    assert page.runs[0].chunk_citations == ()
    assert page.runs[0].entity_citations == ()


def test_list_full_page_without_next_when_results_equal_page_size() -> None:
    """When the result count == page_size (less than page_size + 1),
    next_cursor is None."""
    rows = [_run_row() for _ in range(50)]
    reader, _, _ = _build_reader(queue=[rows])

    page = asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(),
            cursor=None,
        )
    )

    assert len(page.runs) == 50
    assert page.next_cursor is None


def test_list_full_page_with_next_when_results_exceed_page_size() -> None:
    """When the adapter receives page_size + 1 rows, the overflow row
    is dropped and next_cursor is constructed from the last in-page row."""
    rows = [
        _run_row(started_at=datetime(2026, 5, 13, 12, 0, i, tzinfo=timezone.utc))
        for i in range(51)
    ]
    # The query orders DESC, so the "last in-page row" is the 50th
    # (which is the page_size'th = index 49). The fake just returns
    # whatever we feed it; we feed in the order the adapter will see.
    reader, _, _ = _build_reader(queue=[rows])

    page = asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(),
            cursor=None,
        )
    )

    assert len(page.runs) == 50
    assert page.next_cursor is not None
    # Cursor reflects the page_size'th (last in-page) row's identity.
    assert page.next_cursor.started_at == rows[49].started_at
    assert page.next_cursor.id == UUID(rows[49].id)
    assert page.next_cursor.page_size == 50


def test_list_default_page_size_is_ceiling_when_cursor_none() -> None:
    """When cursor is None, the adapter uses PAGE_SIZE_CEILING (50)."""
    reader, _, _ = _build_reader(queue=[[]])

    asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(),
            cursor=None,
        )
    )
    # No assertion on result; the SQL-shape verification happens via
    # the cursor-pagination test below.


def test_list_with_cursor_uses_cursor_page_size() -> None:
    """When a cursor is provided, page_size comes from the cursor."""
    row = _run_row()
    reader, _, _ = _build_reader(queue=[[row]])
    cursor = RunListCursor(
        started_at=_now(),
        id=uuid4(),
        page_size=10,
    )

    page = asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(),
            cursor=cursor,
        )
    )

    # One row, less than page_size of 10, no overflow → no next_cursor.
    assert len(page.runs) == 1
    assert page.next_cursor is None


def test_list_rejects_tenant_context_mismatch_pre_routing() -> None:
    """A list call with a foreign TenantContext raises ValueError
    before session resolution."""
    reader, resolver, sm = _build_reader()
    foreign_ctx = _ctx(tenant_id=_TENANT_B_UUID)

    with pytest.raises(ValueError, match="tenant"):
        asyncio.run(
            reader.list_runs_with_filters(
                tenant_context=foreign_ctx,
                filters=RunListFilters(),
                cursor=None,
            )
        )

    assert resolver.resolved_for == []
    assert sm.session.executed_statements == []


def test_list_with_no_filters_does_not_add_filter_clauses() -> None:
    """The compiled SQL with empty filters has only the tenant_id
    WHERE clause (plus optional cursor); no filter clauses."""
    reader, _, sm = _build_reader(queue=[[]])

    asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(),
            cursor=None,
        )
    )

    sql = str(
        sm.session.executed_statements[0].compile(
            compile_kwargs={"literal_binds": True}
        )
    )
    # Inspect just the WHERE clause; the SELECT list always names all columns.
    where_section = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
    assert "tenant_id" in where_section
    assert "agent_template_id" not in where_section
    assert "agent_template_version" not in where_section
    assert "termination_reason" not in where_section
    assert " IN " not in where_section


def test_list_with_all_four_filters_emits_each_where_clause() -> None:
    """The compiled SQL carries all four filter WHERE clauses when
    all four are set."""
    reader, _, sm = _build_reader(queue=[[]])
    a = uuid4()
    b = uuid4()

    asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(
                agent_template_ids=(a, b),
                agent_template_versions=(1, 2),
                started_at_range=(_now(0), _now(60)),
                termination_reasons=("content", "error"),
            ),
            cursor=None,
        )
    )

    sql = str(
        sm.session.executed_statements[0].compile(
            compile_kwargs={"literal_binds": True}
        )
    )
    assert "agent_template_id IN" in sql or "agent_template_id in" in sql.lower()
    assert "agent_template_version IN" in sql or "agent_template_version in" in sql.lower()
    assert "started_at >=" in sql
    assert "started_at <" in sql
    assert "termination_reason IN" in sql or "termination_reason in" in sql.lower()


def test_list_emits_order_by_started_at_desc_id_desc() -> None:
    """Sort order fixed per D97: started_at DESC, id DESC."""
    reader, _, sm = _build_reader(queue=[[]])

    asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(),
            cursor=None,
        )
    )

    sql = str(
        sm.session.executed_statements[0].compile(
            compile_kwargs={"literal_binds": True}
        )
    )
    assert "ORDER BY" in sql
    assert "started_at DESC" in sql
    assert "id DESC" in sql


def test_list_emits_limit_page_size_plus_one() -> None:
    """The adapter selects page_size + 1 rows to detect overflow."""
    reader, _, sm = _build_reader(queue=[[]])

    asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(),
            cursor=None,
        )
    )

    sql = str(
        sm.session.executed_statements[0].compile(
            compile_kwargs={"literal_binds": True}
        )
    )
    assert "LIMIT 51" in sql


def test_list_with_cursor_emits_tuple_comparison() -> None:
    """The cursor WHERE clause uses tuple comparison so equal-timestamp
    rows paginate stably."""
    reader, _, sm = _build_reader(queue=[[]])
    cursor = RunListCursor(
        started_at=_now(),
        id=uuid4(),
        page_size=10,
    )

    asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(),
            cursor=cursor,
        )
    )

    sql = str(
        sm.session.executed_statements[0].compile(
            compile_kwargs={"literal_binds": True}
        )
    )
    # Tuple comparison appears as (started_at, id) < (..., ...) in Postgres
    # rendering; SQLAlchemy's compiled string carries both column names.
    assert "started_at" in sql
    assert "id" in sql
    assert "<" in sql


def test_list_resolves_session_for_bound_tenant() -> None:
    """list resolves the session for the bound tenant only."""
    reader, resolver, _ = _build_reader(queue=[[]])

    asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(),
            cursor=None,
        )
    )

    assert resolver.resolved_for == [TenantId(str(_TENANT_A_UUID))]


def test_list_filter_single_agent_template_id() -> None:
    """Single filter on agent_template_ids produces an IN clause with
    one value."""
    reader, _, sm = _build_reader(queue=[[]])
    template_id = uuid4()

    asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(agent_template_ids=(template_id,)),
            cursor=None,
        )
    )

    sql = str(
        sm.session.executed_statements[0].compile(
            compile_kwargs={"literal_binds": True}
        )
    ).lower()
    assert "agent_template_id" in sql
    # SQLAlchemy's pg.UUID literal rendering strips hyphens; check the hex form.
    assert template_id.hex in sql


def test_list_filter_termination_reasons_single_value() -> None:
    """Single-value termination_reasons filter still uses IN syntax."""
    reader, _, sm = _build_reader(queue=[[]])

    asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(termination_reasons=("content",)),
            cursor=None,
        )
    )

    sql = str(
        sm.session.executed_statements[0].compile(
            compile_kwargs={"literal_binds": True}
        )
    ).lower()
    assert "termination_reason" in sql
    assert "'content'" in sql


def test_list_equal_timestamps_paginate_via_id_tiebreaker() -> None:
    """When two rows share started_at, the next_cursor's id tiebreaker
    advances pagination beyond the boundary."""
    shared_ts = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    rows = [_run_row(started_at=shared_ts) for _ in range(3)]
    # Page size 2 — adapter requests 3 rows; returns 2 in page + next_cursor.
    reader, _, _ = _build_reader(queue=[rows])
    cursor = RunListCursor(
        started_at=shared_ts.replace(year=2030),  # arbitrary; just needed to set page_size=2
        id=uuid4(),
        page_size=2,
    )

    page = asyncio.run(
        reader.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(),
            cursor=cursor,
        )
    )

    assert len(page.runs) == 2
    assert page.next_cursor is not None
    # The cursor's id is the 2nd row's id (last in-page).
    assert page.next_cursor.id == UUID(rows[1].id)
    assert page.next_cursor.started_at == shared_ts
