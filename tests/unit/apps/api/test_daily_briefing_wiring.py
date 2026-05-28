"""Unit tests for the DailyBriefingReader wiring adapter (D146, S54).

Exercises the two producer-context reads that take injected ports
(``read_intake_records`` in-memory window trim; ``read_audit_events``
timestamp_range filter passthrough) with fakes. ``read_active_cases``
builds a Postgres portfolio reader internally and is verified at the
S54 live-stack smoke.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from apps.api._daily_briefing_wiring import DailyBriefingReaderAdapter
from contexts.audit.domain.audit_event_record import AuditEventRecord
from contexts.audit.domain.chain_integrity import ChainIntegrityVerification
from contexts.audit.domain.query_filters import AuditEventListPage
from contexts.intake.domain import IntakeRecord, IntakeSource, ManualEntryPayload
from contexts.intake.ports.intake_repository import IntakeListPage
from shared_kernel import ActorContext, ActorReference, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000a001"
_NOW = datetime(2026, 5, 28, 6, 0, tzinfo=timezone.utc)
_WINDOW = (_NOW - timedelta(hours=24), _NOW)


def _actor() -> ActorContext:
    role_list = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001",
        role_list=role_list,
        authorisation_set=authorisations_for_roles(role_list),
    )


def _intake(created_at: datetime, text: str) -> IntakeRecord:
    return IntakeRecord(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        intake_source=IntakeSource.WHATSAPP_INBOUND,
        payload=ManualEntryPayload(raw_text=text),
        authored_by=ActorReference(user_id="operator-001"),
        created_at=created_at,
    )


@dataclass
class _FakeIntakeRepository:
    intakes: tuple[IntakeRecord, ...]

    async def save(self, *, tenant_context, intake):  # noqa: ANN001
        raise NotImplementedError

    async def get_by_id(self, *, tenant_context, intake_id):  # noqa: ANN001
        raise NotImplementedError

    async def list_for_tenant(
        self, *, tenant_context, filters, cursor, page_size  # noqa: ANN001
    ) -> IntakeListPage:
        return IntakeListPage(intakes=self.intakes, next_cursor=None)


def _audit_record(ts: datetime) -> AuditEventRecord:
    return AuditEventRecord(
        id=uuid4(),
        tenant_id=_TENANT,
        actor="operator-001",
        jurisdiction="eu-west",
        timestamp=ts,
        action_verb="portfolio.case.create",
        resource_type="case",
        resource_id=str(uuid4()),
        before_state={},
        after_state={"title": "Q3 review"},
        correlation_id="",
        previous_event_hash="0" * 64,
        this_event_hash="a" * 64,
    )


@dataclass
class _FakeAuditEventReader:
    events: tuple[AuditEventRecord, ...]
    seen_filters: list = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.seen_filters = []

    async def get_audit_event(self, **kwargs):  # noqa: ANN003
        raise NotImplementedError

    async def list_audit_events_with_filters(
        self, *, destination, filters, cursor, page_size, tenant_context  # noqa: ANN001
    ) -> AuditEventListPage:
        self.seen_filters.append(filters)
        return AuditEventListPage(
            events=self.events,
            next_cursor=None,
            chain_integrity=ChainIntegrityVerification(status="verified"),
        )

    async def verify_chain_segment(self, **kwargs):  # noqa: ANN003
        raise NotImplementedError


def _adapter(intakes, events) -> DailyBriefingReaderAdapter:
    async def _sf(_tc):  # noqa: ANN001
        raise AssertionError("portfolio reader path not exercised in this test")

    return DailyBriefingReaderAdapter(
        session_factory_for_tenant=_sf,
        intake_repository=_FakeIntakeRepository(intakes=intakes),
        audit_event_reader=_FakeAuditEventReader(events=events),
    )


def test_read_intake_records_trims_to_window() -> None:
    inside = _intake(_NOW - timedelta(hours=2), "inside window")
    older = _intake(_NOW - timedelta(hours=48), "older than window")
    adapter = _adapter((inside, older), ())
    records = asyncio.run(
        adapter.read_intake_records(actor=_actor(), window=_WINDOW)
    )
    assert len(records) == 1
    assert records[0].intake_id == inside.id
    assert records[0].summary == "inside window"
    assert records[0].intake_source == "WHATSAPP_INBOUND"


def test_read_audit_events_passes_timestamp_range_filter() -> None:
    event = _audit_record(_NOW - timedelta(hours=1))
    reader = _FakeAuditEventReader(events=(event,))

    async def _sf(_tc):  # noqa: ANN001
        raise AssertionError("portfolio path not exercised")

    from apps.api._daily_briefing_wiring import DailyBriefingReaderAdapter as Adapter

    adapter = Adapter(
        session_factory_for_tenant=_sf,
        intake_repository=_FakeIntakeRepository(intakes=()),
        audit_event_reader=reader,
    )
    events = asyncio.run(
        adapter.read_audit_events(actor=_actor(), window=_WINDOW)
    )
    assert len(events) == 1
    assert events[0].action_verb == "portfolio.case.create"
    # the adapter passed a timestamp_range filter matching the window
    assert reader.seen_filters[0].timestamp_range == _WINDOW
