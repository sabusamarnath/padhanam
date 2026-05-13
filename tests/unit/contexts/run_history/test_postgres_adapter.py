"""Unit tests for PostgresRunHistoryAdapter (D95, D96; S31, S32).

Concerns:

1. The adapter issues an INSERT into ``runs`` with the D95 column
   set (15 columns).
2. D96 / S32: citation rows on the same RunRecord land within the
   same transaction (chunk_citations and entity_citations both
   touch their respective tables; empty citation tuples produce
   no extra INSERTs).
3. Tenant-isolation defence-in-depth: a RunRecord whose
   ``tenant_id`` does not match the adapter's bound tenant raises
   ValueError before any session resolution or insert; the same
   defence applies to each citation row's tenant_id.
4. The session resolver is called with the bound tenant_id, not
   any other value (cross-tenant write attempt cannot route to
   the wrong database).
5. The persist operation uses ``async with session.begin()`` so
   any insert failure rolls the whole transaction back per D96's
   single-transaction multi-table write commitment.

Uses a fake async sessionmaker that records executed statements,
avoiding a live Postgres dependency. The migration's SQL shape
is exercised by the live-stack smoke.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa

from contexts.run_history.adapters.outbound.postgres.repository import (
    PostgresRunHistoryAdapter,
    run_chunk_citations,
    run_entity_citations,
    runs,
)
from contexts.run_history.domain.citation_records import (
    ChunkCitationRecord,
    EntityCitationRecord,
)
from contexts.run_history.domain.run_record import RunRecord
from shared_kernel import TenantId


def _make_record(
    tenant_id: str = "tenant-a",
    *,
    chunk_citations: tuple = (),
    entity_citations: tuple = (),
) -> RunRecord:
    return RunRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        agent_template_id=uuid4(),
        agent_template_version=1,
        input_message="hello",
        output_content="hi",
        started_at=datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 5, 13, 12, 1, 0, tzinfo=timezone.utc),
        termination_reason="content",
        iteration_count=1,
        total_cost_usd=Decimal("0.001"),
        trace_id=None,
        audit_start_hash="0" * 64,
        audit_end_hash="1" * 64,
        created_at=datetime(2026, 5, 13, 12, 1, 5, tzinfo=timezone.utc),
        chunk_citations=chunk_citations,
        entity_citations=entity_citations,
    )


def _make_chunk_record(*, run_id, tenant_id="tenant-a", excerpt="cited content"):
    return ChunkCitationRecord(
        id=uuid4(),
        run_id=run_id,
        chunk_id=uuid4(),
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        chunk_excerpt=excerpt,
        source_snapshot={"file_name": "doc.pdf", "file_type": "application/pdf"},
    )


def _make_entity_record(*, run_id, tenant_id="tenant-a", name="Acme"):
    return EntityCitationRecord(
        id=uuid4(),
        run_id=run_id,
        entity_tenant_id=tenant_id,
        entity_name=name,
        entity_type="Organization",
        tenant_id=tenant_id,
        source_chunk_ids=(uuid4(),),
    )


class _FakeTransaction:
    """Fake async context manager returned by session.begin()."""

    def __init__(self, session: "_FakeSession") -> None:
        self._session = session

    async def __aenter__(self) -> "_FakeSession":
        self._session.in_transaction = True
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self._session.committed = True
        else:
            self._session.rolled_back = True
        self._session.in_transaction = False


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[Any] = []
        self.executed_payloads: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.in_transaction = False
        self._fail_on_table = None

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction(self)

    async def execute(self, statement: Any, payload: Any = None) -> None:
        if self._fail_on_table is not None:
            table = getattr(statement, "table", None)
            if table is self._fail_on_table:
                raise RuntimeError("simulated insert failure")
        self.executed.append(statement)
        self.executed_payloads.append(payload)

    async def commit(self) -> None:
        self.committed = True

    async def close(self) -> None:
        pass

    def fail_on(self, table) -> None:
        self._fail_on_table = table


class _FakeSessionmaker:
    def __init__(self) -> None:
        self.session = _FakeSession()

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

    async def __call__(
        self, tenant_id: TenantId
    ) -> _FakeSessionmaker:
        self.resolved_for.append(tenant_id)
        return self._sessionmaker


def test_persist_issues_insert_into_runs_within_transaction() -> None:
    sm = _FakeSessionmaker()
    resolver = _Resolver(sm)
    bound = TenantId("tenant-a")
    adapter = PostgresRunHistoryAdapter(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=bound,
    )

    record = _make_record(tenant_id="tenant-a")
    asyncio.run(adapter.persist(record))

    # D96: the transaction commits on success per the async with
    # session.begin() block; one INSERT lands when no citations.
    assert sm.session.committed is True
    assert sm.session.rolled_back is False
    assert len(sm.session.executed) == 1
    stmt = sm.session.executed[0]
    assert getattr(stmt, "table", None) is runs


def test_persist_writes_no_citation_inserts_for_empty_tuples() -> None:
    """D96: empty chunk_citations and empty entity_citations produce
    no INSERTs into the citation tables; the runs row commits cleanly."""
    sm = _FakeSessionmaker()
    resolver = _Resolver(sm)
    bound = TenantId("tenant-a")
    adapter = PostgresRunHistoryAdapter(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=bound,
    )

    record = _make_record(tenant_id="tenant-a")
    asyncio.run(adapter.persist(record))

    citation_tables = {run_chunk_citations, run_entity_citations}
    for stmt in sm.session.executed:
        assert getattr(stmt, "table", None) not in citation_tables, (
            "citation tables must not be touched when citation tuples are empty"
        )


def test_persist_rejects_tenant_id_mismatch() -> None:
    """Defence-in-depth per D24 / D32: a RunRecord whose tenant_id
    does not match the adapter's bound tenant raises before any
    session resolution. The session resolver must not be called.
    """
    sm = _FakeSessionmaker()
    resolver = _Resolver(sm)
    bound = TenantId("tenant-a")
    adapter = PostgresRunHistoryAdapter(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=bound,
    )

    foreign_record = _make_record(tenant_id="tenant-b")
    with pytest.raises(ValueError, match="tenant"):
        asyncio.run(adapter.persist(foreign_record))

    assert resolver.resolved_for == []
    assert sm.session.executed == []
    assert sm.session.committed is False


def test_persist_resolves_session_for_bound_tenant_only() -> None:
    """The resolver is called with the adapter's bound tenant_id
    exactly, never any other value (no cross-tenant routing
    possible by construction)."""
    sm = _FakeSessionmaker()
    resolver = _Resolver(sm)
    bound = TenantId("tenant-a")
    adapter = PostgresRunHistoryAdapter(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=bound,
    )

    record = _make_record(tenant_id="tenant-a")
    asyncio.run(adapter.persist(record))

    assert resolver.resolved_for == [bound]


def test_persist_insert_carries_all_fifteen_columns() -> None:
    """The insert values dict must carry every D95 column; missing
    a NOT NULL column would raise at the database. The fake
    session records the bound parameters; we inspect via
    SQLAlchemy's compiled-statement parameters."""
    sm = _FakeSessionmaker()
    resolver = _Resolver(sm)
    bound = TenantId("tenant-a")
    adapter = PostgresRunHistoryAdapter(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=bound,
    )

    record = _make_record(tenant_id="tenant-a")
    asyncio.run(adapter.persist(record))

    stmt = sm.session.executed[0]
    # Insert.compile() exposes the bound parameters keyed by column.
    compiled = stmt.compile(
        dialect=sa.dialects.postgresql.dialect(),
        compile_kwargs={"literal_binds": False},
    )
    bound_param_names = set(compiled.params.keys())
    expected = {
        "id",
        "tenant_id",
        "jurisdiction",
        "agent_template_id",
        "agent_template_version",
        "input_message",
        "output_content",
        "started_at",
        "completed_at",
        "termination_reason",
        "iteration_count",
        "total_cost_usd",
        "trace_id",
        "audit_start_hash",
        "audit_end_hash",
        "created_at",
    }
    assert bound_param_names == expected, (
        f"insert column set drifted from D95: "
        f"unexpected={bound_param_names - expected}, "
        f"missing={expected - bound_param_names}"
    )


# ---------------------------------------------------------------------------
# D96 / S32: single-transaction multi-table writes
# ---------------------------------------------------------------------------


def test_persist_writes_runs_plus_chunk_plus_entity_in_single_transaction() -> None:
    """D96: with three chunk citations and two entity citations on
    the RunRecord, the adapter issues three INSERTs in this order
    inside a single transaction: runs, run_chunk_citations,
    run_entity_citations."""
    sm = _FakeSessionmaker()
    resolver = _Resolver(sm)
    bound = TenantId("tenant-a")
    adapter = PostgresRunHistoryAdapter(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=bound,
    )

    run_id = uuid4()
    chunks = tuple(
        _make_chunk_record(run_id=run_id, excerpt=f"chunk-{i}") for i in range(3)
    )
    entities = tuple(
        _make_entity_record(run_id=run_id, name=f"Entity-{i}") for i in range(2)
    )
    record = _make_record(
        tenant_id="tenant-a",
        chunk_citations=chunks,
        entity_citations=entities,
    )
    # Override the id so chunks reference it correctly.
    record = RunRecord(**{**record.__dict__, "id": run_id})
    asyncio.run(adapter.persist(record))

    assert sm.session.committed is True
    assert sm.session.rolled_back is False
    assert len(sm.session.executed) == 3
    assert getattr(sm.session.executed[0], "table", None) is runs
    assert getattr(sm.session.executed[1], "table", None) is run_chunk_citations
    assert getattr(sm.session.executed[2], "table", None) is run_entity_citations
    # The bulk INSERTs carry row-count-many payloads.
    assert len(sm.session.executed_payloads[1]) == 3
    assert len(sm.session.executed_payloads[2]) == 2


def test_persist_chunk_citation_insert_failure_rolls_whole_transaction_back() -> None:
    """D96: insert failure on the chunk citations table rolls the
    runs row back too; nothing commits."""
    sm = _FakeSessionmaker()
    sm.session.fail_on(run_chunk_citations)
    resolver = _Resolver(sm)
    bound = TenantId("tenant-a")
    adapter = PostgresRunHistoryAdapter(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=bound,
    )

    run_id = uuid4()
    record = _make_record(
        tenant_id="tenant-a",
        chunk_citations=(_make_chunk_record(run_id=run_id),),
    )
    record = RunRecord(**{**record.__dict__, "id": run_id})

    with pytest.raises(RuntimeError, match="simulated insert failure"):
        asyncio.run(adapter.persist(record))

    # The transaction rolled back; committed False, rolled_back True.
    assert sm.session.committed is False
    assert sm.session.rolled_back is True


def test_persist_entity_citation_insert_failure_rolls_whole_transaction_back() -> None:
    """D96: failure on the entity-citations insert (the third in the
    sequence) rolls runs + chunk_citations + entity_citations all back."""
    sm = _FakeSessionmaker()
    sm.session.fail_on(run_entity_citations)
    resolver = _Resolver(sm)
    bound = TenantId("tenant-a")
    adapter = PostgresRunHistoryAdapter(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=bound,
    )

    run_id = uuid4()
    record = _make_record(
        tenant_id="tenant-a",
        chunk_citations=(_make_chunk_record(run_id=run_id),),
        entity_citations=(_make_entity_record(run_id=run_id),),
    )
    record = RunRecord(**{**record.__dict__, "id": run_id})

    with pytest.raises(RuntimeError, match="simulated insert failure"):
        asyncio.run(adapter.persist(record))

    assert sm.session.committed is False
    assert sm.session.rolled_back is True


def test_persist_rejects_chunk_citation_tenant_id_mismatch() -> None:
    """D96 / D24: defence-in-depth extends to citation rows; a
    chunk-citation row whose tenant_id does not match the bound
    tenant raises before any session resolution."""
    sm = _FakeSessionmaker()
    resolver = _Resolver(sm)
    bound = TenantId("tenant-a")
    adapter = PostgresRunHistoryAdapter(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=bound,
    )

    run_id = uuid4()
    foreign_chunk = _make_chunk_record(run_id=run_id, tenant_id="tenant-b")
    record = _make_record(
        tenant_id="tenant-a",
        chunk_citations=(foreign_chunk,),
    )
    record = RunRecord(**{**record.__dict__, "id": run_id})

    with pytest.raises(ValueError, match="ChunkCitationRecord.tenant_id"):
        asyncio.run(adapter.persist(record))

    assert resolver.resolved_for == []
    assert sm.session.executed == []


def test_persist_rejects_entity_citation_tenant_id_mismatch() -> None:
    """D96 / D24: defence-in-depth extends to entity citation rows."""
    sm = _FakeSessionmaker()
    resolver = _Resolver(sm)
    bound = TenantId("tenant-a")
    adapter = PostgresRunHistoryAdapter(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=bound,
    )

    run_id = uuid4()
    foreign_entity = _make_entity_record(run_id=run_id, tenant_id="tenant-b")
    record = _make_record(
        tenant_id="tenant-a",
        entity_citations=(foreign_entity,),
    )
    record = RunRecord(**{**record.__dict__, "id": run_id})

    with pytest.raises(ValueError, match="EntityCitationRecord.tenant_id"):
        asyncio.run(adapter.persist(record))

    assert resolver.resolved_for == []
    assert sm.session.executed == []
