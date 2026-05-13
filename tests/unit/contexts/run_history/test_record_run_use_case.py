"""Unit tests for the record_run use case (D75, D95, S31 commit 3).

Three concerns:

1. Happy path: an authenticated principal plus a valid RunRecord
   plus a fake repository produces the expected persist call.
2. Auth boundary: an unauthenticated principal (empty role set)
   raises AuthorizationError and the repository is not touched.
3. Repository failure surfaces through the use case (no swallow).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from contexts.run_history.application.use_cases import record_run
from contexts.run_history.domain.run_record import RunRecord
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from padhanam.security import AuthorizationError, OPERATOR_ROLE, Principal
from shared_kernel import TenantId


def _make_run_record() -> RunRecord:
    return RunRecord(
        id=uuid4(),
        tenant_id="tenant-a",
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


class _FakeRepository:
    def __init__(self) -> None:
        self.persisted: list[RunRecord] = []
        self.raise_on_persist: Exception | None = None

    async def persist(self, record: RunRecord) -> None:
        if self.raise_on_persist is not None:
            raise self.raise_on_persist
        self.persisted.append(record)


class _CollectingSecurityEvents:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


def _operator_principal() -> Principal:
    return Principal(
        subject="alice",
        tenant_id=TenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="x",
    )


def _tenant_principal() -> Principal:
    return Principal(
        subject="bob",
        tenant_id=TenantId("tenant-a"),
        roles=frozenset({"audit.read"}),
        credential_ref="x",
    )


def _unauthenticated_principal() -> Principal:
    return Principal(
        subject="anon",
        tenant_id=TenantId("tenant-a"),
        roles=frozenset(),
        credential_ref="x",
    )


def test_record_run_persists_via_repository_for_operator_principal() -> None:
    repo = _FakeRepository()
    sec = _CollectingSecurityEvents()
    run_record = _make_run_record()

    asyncio.run(
        record_run(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            run_record=run_record,
        )
    )

    assert repo.persisted == [run_record]
    assert sec.events == []


def test_record_run_persists_via_repository_for_tenant_principal() -> None:
    """Tenant-context auth posture matches D75 CRUD use cases."""
    repo = _FakeRepository()
    sec = _CollectingSecurityEvents()
    run_record = _make_run_record()

    asyncio.run(
        record_run(
            principal=_tenant_principal(),
            repository=repo,
            security_events=sec,
            run_record=run_record,
        )
    )

    assert repo.persisted == [run_record]
    assert sec.events == []


def test_record_run_denies_unauthenticated_principal() -> None:
    repo = _FakeRepository()
    sec = _CollectingSecurityEvents()
    run_record = _make_run_record()

    with pytest.raises(AuthorizationError, match="record_run"):
        asyncio.run(
            record_run(
                principal=_unauthenticated_principal(),
                repository=repo,
                security_events=sec,
                run_record=run_record,
            )
        )

    assert repo.persisted == []
    assert len(sec.events) == 1
    event = sec.events[0]
    assert event.category is SecurityEventCategory.AUTHZ_DENIAL
    assert event.action == "run_history.record_run"
    assert event.outcome == "deny"
    assert event.resource_ref == f"runs:{run_record.id}"


def test_record_run_propagates_repository_failure() -> None:
    repo = _FakeRepository()
    repo.raise_on_persist = RuntimeError("connection refused")
    sec = _CollectingSecurityEvents()
    run_record = _make_run_record()

    with pytest.raises(RuntimeError, match="connection refused"):
        asyncio.run(
            record_run(
                principal=_operator_principal(),
                repository=repo,
                security_events=sec,
                run_record=run_record,
            )
        )

    assert repo.persisted == []
