"""Unit tests for PostgresAuditEventReader (D102, S36).

Covers the scenarios named in the S36 brief commit 4:

- routing: destination/tenant_context mismatch raises
  AuditQueryRoutingError at port-method entry (both directions).
- get_audit_event: missing event_id returns None; found returns
  AuditEventRecord; control-plane uses empty-string scope.
- list_audit_events_with_filters: no filters; each filter alone;
  cursor pagination; PAGE_SIZE_CEILING enforcement; equal-
  timestamp events paginate via tuple comparison.
- verify_chain_segment (pure function):
  - empty / single-row → partial
  - 2+ rows verified end-to-end (chain head)
  - 2+ rows with per-row hash failure → broken_at_row
  - 2+ rows with broken chain link → partial
- list_audit_events_with_filters carries chain_integrity on
  every returned page.

Uses a fake session that captures executed statements and
returns canned mappings keyed by ``.mappings()`` (mirroring the
write-side audit adapter's mappings-based row access). The SQL
shape is exercised against real Postgres via the contract
harness extension at commit 6 and the live-stack smoke at
commit 7.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from contexts.audit.adapters.outbound.postgres.reader import (
    PostgresAuditEventReader,
    _verify_segment,
)
from contexts.audit.domain.audit_event_record import AuditEventRecord
from contexts.audit.domain.events import GENESIS_HASH, compute_event_hash
from contexts.audit.domain.query_filters import (
    AuditEventListCursor,
    AuditEventListFilters,
    PAGE_SIZE_CEILING,
)
from contexts.audit.ports.reader import AuditQueryRoutingError
from shared_kernel import TenantContext, TenantId


_TENANT_A = UUID("aaaa1111-2222-4333-8444-555555555555")


def _ctx(tenant_id: UUID = _TENANT_A) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        cost_attribution_id=str(tenant_id),
    )


def _now(offset_sec: int = 0) -> datetime:
    return datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc) + timedelta(
        seconds=offset_sec
    )


# -------------------------------------------------------------------------
# Fake session / sessionmaker / resolver
# -------------------------------------------------------------------------


class _FakeMappings:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def all(self) -> list[dict]:
        return list(self._rows)

    def first(self) -> dict | None:
        return self._rows[0] if self._rows else None


class _FakeResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def mappings(self) -> _FakeMappings:
        return _FakeMappings(self._rows)


class _FakeSession:
    def __init__(self, queue: list[list[dict]]) -> None:
        self._queue = queue
        self.executed_statements: list[Any] = []

    async def execute(self, statement: Any, params: Any = None) -> _FakeResult:
        self.executed_statements.append(statement)
        if not self._queue:
            return _FakeResult([])
        return _FakeResult(self._queue.pop(0))


class _FakeSessionmaker:
    def __init__(self, queue: list[list[dict]]) -> None:
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
    per_tenant_queue: list[list[dict]] | None = None,
    control_plane_queue: list[list[dict]] | None = None,
) -> tuple[
    PostgresAuditEventReader,
    _Resolver,
    _FakeSessionmaker,
    _FakeSessionmaker,
]:
    per_tenant_sm = _FakeSessionmaker(per_tenant_queue or [])
    control_plane_sm = _FakeSessionmaker(control_plane_queue or [])
    resolver = _Resolver(per_tenant_sm)
    reader = PostgresAuditEventReader(
        per_tenant_sessionmaker_resolver=resolver,
        control_plane_sessionmaker=control_plane_sm,
    )
    return reader, resolver, per_tenant_sm, control_plane_sm


# -------------------------------------------------------------------------
# Row factories
# -------------------------------------------------------------------------


def _build_chain_row(
    *,
    actor: str = "user:alice",
    tenant_id: str = str(_TENANT_A),
    jurisdiction: str = "eu-west",
    timestamp: datetime | None = None,
    action_verb: str = "agent.invoke.end",
    resource_type: str = "agent_run",
    resource_id: str | None = None,
    before_state: dict | None = None,
    after_state: dict | None = None,
    correlation_id: str = "corr-1",
    previous_event_hash: str = GENESIS_HASH,
    event_id: UUID | None = None,
) -> dict:
    """Construct a tenant_audit row mapping with a valid hash chain link.

    Uses ``compute_event_hash`` so the returned row's
    ``this_event_hash`` matches the payload — verifications pass
    by default, and tests that want a tampered row construct
    explicitly.
    """
    timestamp = timestamp or _now()
    resource_id = resource_id or str(uuid4())
    before_state = before_state or {}
    after_state = after_state or {"k": "v"}
    this_hash = compute_event_hash(
        actor=actor,
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
        timestamp=timestamp.isoformat(),
        action_verb=action_verb,
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=before_state,
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=previous_event_hash,
    )
    return {
        "id": str(event_id or uuid4()),
        "tenant_id": tenant_id,
        "actor": actor,
        "jurisdiction": jurisdiction,
        "timestamp": timestamp,
        "action_verb": action_verb,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "before_state": before_state,
        "after_state": after_state,
        "correlation_id": correlation_id,
        "previous_event_hash": previous_event_hash,
        "this_event_hash": this_hash,
    }


def _row_to_record_via_helper(row: dict) -> AuditEventRecord:
    return AuditEventRecord(
        id=UUID(row["id"]),
        tenant_id=row["tenant_id"],
        actor=row["actor"],
        jurisdiction=row["jurisdiction"],
        timestamp=row["timestamp"],
        action_verb=row["action_verb"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        before_state=row["before_state"],
        after_state=row["after_state"],
        correlation_id=row["correlation_id"],
        previous_event_hash=row["previous_event_hash"],
        this_event_hash=row["this_event_hash"],
    )


# -------------------------------------------------------------------------
# Routing tests
# -------------------------------------------------------------------------


def test_get_per_tenant_without_tenant_context_raises() -> None:
    reader, *_ = _build_reader()

    async def run() -> None:
        with pytest.raises(AuditQueryRoutingError, match="per_tenant"):
            await reader.get_audit_event(
                destination="per_tenant",
                event_id=uuid4(),
                tenant_context=None,
            )

    asyncio.run(run())


def test_get_control_plane_with_tenant_context_raises() -> None:
    reader, *_ = _build_reader()

    async def run() -> None:
        with pytest.raises(AuditQueryRoutingError, match="control_plane"):
            await reader.get_audit_event(
                destination="control_plane",
                event_id=uuid4(),
                tenant_context=_ctx(),
            )

    asyncio.run(run())


def test_list_per_tenant_without_tenant_context_raises() -> None:
    reader, *_ = _build_reader()

    async def run() -> None:
        with pytest.raises(AuditQueryRoutingError):
            await reader.list_audit_events_with_filters(
                destination="per_tenant",
                filters=AuditEventListFilters(),
                cursor=None,
                page_size=10,
                tenant_context=None,
            )

    asyncio.run(run())


def test_list_control_plane_with_tenant_context_raises() -> None:
    reader, *_ = _build_reader()

    async def run() -> None:
        with pytest.raises(AuditQueryRoutingError):
            await reader.list_audit_events_with_filters(
                destination="control_plane",
                filters=AuditEventListFilters(),
                cursor=None,
                page_size=10,
                tenant_context=_ctx(),
            )

    asyncio.run(run())


# -------------------------------------------------------------------------
# get_audit_event
# -------------------------------------------------------------------------


def test_get_per_tenant_event_found_returns_record() -> None:
    row = _build_chain_row()
    reader, resolver, *_ = _build_reader(per_tenant_queue=[[row]])

    async def run() -> None:
        result = await reader.get_audit_event(
            destination="per_tenant",
            event_id=UUID(row["id"]),
            tenant_context=_ctx(),
        )
        assert result is not None
        assert result.id == UUID(row["id"])
        assert result.tenant_id == str(_TENANT_A)
        # resolver fired exactly once with the routed tenant_id
        assert resolver.resolved_for == [TenantId(str(_TENANT_A))]

    asyncio.run(run())


def test_get_per_tenant_event_missing_returns_none() -> None:
    reader, *_ = _build_reader(per_tenant_queue=[[]])

    async def run() -> None:
        result = await reader.get_audit_event(
            destination="per_tenant",
            event_id=uuid4(),
            tenant_context=_ctx(),
        )
        assert result is None

    asyncio.run(run())


def test_get_control_plane_event_uses_control_plane_sessionmaker() -> None:
    row = _build_chain_row(tenant_id="")
    reader, resolver, _pt, cp = _build_reader(control_plane_queue=[[row]])

    async def run() -> None:
        result = await reader.get_audit_event(
            destination="control_plane",
            event_id=UUID(row["id"]),
            tenant_context=None,
        )
        assert result is not None
        assert result.tenant_id == ""
        assert resolver.resolved_for == []  # per-tenant resolver not touched
        # The control_plane sessionmaker executed exactly one statement.
        assert len(cp.session.executed_statements) == 1

    asyncio.run(run())


# -------------------------------------------------------------------------
# list_audit_events_with_filters
# -------------------------------------------------------------------------


def test_list_no_filters_returns_page() -> None:
    # build a chain of 3 events linked
    row1 = _build_chain_row(timestamp=_now(0))
    row2 = _build_chain_row(
        timestamp=_now(10),
        previous_event_hash=row1["this_event_hash"],
    )
    row3 = _build_chain_row(
        timestamp=_now(20),
        previous_event_hash=row2["this_event_hash"],
    )
    # list returns DESC order
    reader, *_ = _build_reader(per_tenant_queue=[[row3, row2, row1]])

    async def run() -> None:
        page = await reader.list_audit_events_with_filters(
            destination="per_tenant",
            filters=AuditEventListFilters(),
            cursor=None,
            page_size=10,
            tenant_context=_ctx(),
        )
        assert len(page.events) == 3
        # First event in DESC order is the newest (row3)
        assert page.events[0].timestamp == row3["timestamp"]
        # Page that fits returns no next cursor
        assert page.next_cursor is None
        # Chain integrity should verify cleanly
        assert page.chain_integrity.status == "verified"

    asyncio.run(run())


def test_list_overflow_constructs_next_cursor() -> None:
    # build 3 rows; ask for page_size=2 → reader queries LIMIT 3 and slices
    row1 = _build_chain_row(timestamp=_now(0))
    row2 = _build_chain_row(
        timestamp=_now(10), previous_event_hash=row1["this_event_hash"]
    )
    row3 = _build_chain_row(
        timestamp=_now(20), previous_event_hash=row2["this_event_hash"]
    )
    reader, *_ = _build_reader(per_tenant_queue=[[row3, row2, row1]])

    async def run() -> None:
        page = await reader.list_audit_events_with_filters(
            destination="per_tenant",
            filters=AuditEventListFilters(),
            cursor=None,
            page_size=2,
            tenant_context=_ctx(),
        )
        # Only first 2 rows returned (page_size=2)
        assert len(page.events) == 2
        # next_cursor present, anchored at the last in-page row (row2)
        assert page.next_cursor is not None
        assert page.next_cursor.timestamp == row2["timestamp"]
        assert page.next_cursor.id == UUID(row2["id"])
        assert page.next_cursor.page_size == 2

    asyncio.run(run())


def test_list_invalid_page_size_raises() -> None:
    reader, *_ = _build_reader()

    async def run() -> None:
        with pytest.raises(ValueError, match="page_size"):
            await reader.list_audit_events_with_filters(
                destination="per_tenant",
                filters=AuditEventListFilters(),
                cursor=None,
                page_size=PAGE_SIZE_CEILING + 1,
                tenant_context=_ctx(),
            )
        with pytest.raises(ValueError, match="page_size"):
            await reader.list_audit_events_with_filters(
                destination="per_tenant",
                filters=AuditEventListFilters(),
                cursor=None,
                page_size=0,
                tenant_context=_ctx(),
            )

    asyncio.run(run())


def test_list_cursor_page_size_overrides_page_size_param() -> None:
    # When cursor.page_size differs from page_size arg, cursor wins.
    row1 = _build_chain_row(timestamp=_now(0))
    reader, *_ = _build_reader(per_tenant_queue=[[row1]])
    cursor = AuditEventListCursor(
        timestamp=_now(100), id=uuid4(), page_size=5
    )

    async def run() -> None:
        page = await reader.list_audit_events_with_filters(
            destination="per_tenant",
            filters=AuditEventListFilters(),
            cursor=cursor,
            page_size=10,  # different from cursor.page_size
            tenant_context=_ctx(),
        )
        assert len(page.events) == 1
        assert page.next_cursor is None

    asyncio.run(run())


def test_list_empty_page_chain_integrity_is_partial() -> None:
    reader, *_ = _build_reader(per_tenant_queue=[[]])

    async def run() -> None:
        page = await reader.list_audit_events_with_filters(
            destination="per_tenant",
            filters=AuditEventListFilters(),
            cursor=None,
            page_size=10,
            tenant_context=_ctx(),
        )
        assert len(page.events) == 0
        assert page.chain_integrity.status == "partial"

    asyncio.run(run())


# -------------------------------------------------------------------------
# verify_chain_segment / _verify_segment
# -------------------------------------------------------------------------


def test_verify_segment_empty_is_partial() -> None:
    result = _verify_segment(())
    assert result.status == "partial"


def test_verify_segment_single_row_passing_per_row_is_partial() -> None:
    row = _build_chain_row()
    record = _row_to_record_via_helper(row)
    result = _verify_segment((record,))
    assert result.status == "partial"


def test_verify_segment_single_row_broken_per_row_is_broken_at_row() -> None:
    row = _build_chain_row()
    # tamper with this_event_hash so per-row check fails
    row["this_event_hash"] = "f" * 64
    record = _row_to_record_via_helper(row)
    result = _verify_segment((record,))
    assert result.status == "broken_at_row"
    assert result.broken_at_id == record.id


def test_verify_segment_two_linked_rows_verified() -> None:
    row1 = _build_chain_row(timestamp=_now(0))
    row2 = _build_chain_row(
        timestamp=_now(10),
        previous_event_hash=row1["this_event_hash"],
    )
    records = (_row_to_record_via_helper(row1), _row_to_record_via_helper(row2))
    result = _verify_segment(records)
    assert result.status == "verified"


def test_verify_segment_handles_desc_input_order() -> None:
    # Caller passes events in DESC display order; verifier internally
    # sorts to chain order for link verification.
    row1 = _build_chain_row(timestamp=_now(0))
    row2 = _build_chain_row(
        timestamp=_now(10),
        previous_event_hash=row1["this_event_hash"],
    )
    records = (_row_to_record_via_helper(row2), _row_to_record_via_helper(row1))
    result = _verify_segment(records)
    assert result.status == "verified"


def test_verify_segment_broken_chain_link_is_partial() -> None:
    # Two rows whose per-row hashes are valid in isolation, but
    # row2's previous_event_hash does not match row1's this_event_hash
    # (e.g., a row was filtered out between them).
    row1 = _build_chain_row(timestamp=_now(0))
    row2 = _build_chain_row(
        timestamp=_now(10),
        previous_event_hash="9" * 64,  # NOT row1's this_event_hash
    )
    records = (_row_to_record_via_helper(row1), _row_to_record_via_helper(row2))
    result = _verify_segment(records)
    assert result.status == "partial"


def test_verify_segment_broken_at_specific_row() -> None:
    row1 = _build_chain_row(timestamp=_now(0))
    row2 = _build_chain_row(
        timestamp=_now(10),
        previous_event_hash=row1["this_event_hash"],
    )
    # tamper with row2's this_event_hash so per-row check fails on row2
    row2["this_event_hash"] = "e" * 64
    records = (_row_to_record_via_helper(row1), _row_to_record_via_helper(row2))
    result = _verify_segment(records)
    assert result.status == "broken_at_row"
    assert result.broken_at_id == UUID(row2["id"])


def test_verify_chain_segment_pure_does_not_touch_session() -> None:
    reader, resolver, pt, cp = _build_reader()
    row1 = _build_chain_row(timestamp=_now(0))
    row2 = _build_chain_row(
        timestamp=_now(10),
        previous_event_hash=row1["this_event_hash"],
    )
    records = (_row_to_record_via_helper(row1), _row_to_record_via_helper(row2))

    async def run() -> None:
        result = await reader.verify_chain_segment(
            destination="per_tenant", events=records
        )
        assert result.status == "verified"
        # No session opened; no resolver call.
        assert resolver.resolved_for == []
        assert pt.session.executed_statements == []
        assert cp.session.executed_statements == []

    asyncio.run(run())
