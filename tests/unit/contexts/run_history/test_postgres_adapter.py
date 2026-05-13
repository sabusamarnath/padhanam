"""Unit tests for PostgresRunHistoryAdapter (D95, S31 commit 4).

Three concerns:

1. The adapter issues a single INSERT into ``runs`` with the
   correct column set per D95 (15 columns, no citation tables
   touched at S31).
2. Tenant-isolation defence-in-depth: a RunRecord whose
   ``tenant_id`` does not match the adapter's bound tenant raises
   ValueError before any session resolution or insert.
3. The session resolver is called with the bound tenant_id, not
   any other value (cross-tenant write attempt cannot route to
   the wrong database).

Uses a fake async sessionmaker that records executed statements,
avoiding a live Postgres dependency. The migration's SQL shape
is exercised by the live-stack smoke at S31 commit 8.
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
from contexts.run_history.domain.run_record import RunRecord
from shared_kernel import TenantId


def _make_record(tenant_id: str = "tenant-a") -> RunRecord:
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
    )


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[Any] = []
        self.committed = False

    async def execute(self, statement: Any) -> None:
        self.executed.append(statement)

    async def commit(self) -> None:
        self.committed = True

    async def close(self) -> None:
        pass


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


def test_persist_issues_single_insert_into_runs() -> None:
    sm = _FakeSessionmaker()
    resolver = _Resolver(sm)
    bound = TenantId("tenant-a")
    adapter = PostgresRunHistoryAdapter(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=bound,
    )

    record = _make_record(tenant_id="tenant-a")
    asyncio.run(adapter.persist(record))

    assert sm.session.committed is True
    assert len(sm.session.executed) == 1
    stmt = sm.session.executed[0]
    # The statement targets the `runs` table; SQLAlchemy renders
    # Insert.table as the bound Table object.
    assert getattr(stmt, "table", None) is runs


def test_persist_writes_no_citation_rows_at_s31() -> None:
    """S31 commits the runs row only; citation tables exist but
    no citation INSERTs land until S32 per the p9-epic forecast."""
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
            "citation tables must not be touched at S31; population lands at S32"
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
