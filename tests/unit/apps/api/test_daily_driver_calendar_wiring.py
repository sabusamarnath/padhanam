"""Tenant-isolation + today-window tests for the calendar reader adapter (D159, D24).

The ``CalendarEventsReaderAdapter`` composes the calendar context's
PostgresMeetingStore bound to the request's tenant, filters to the current
day, and maps each Meeting onto the daily-driver ``CalendarToday``
projection. These tests stub the store to assert the isolation invariant
(red-team shaped: the store is constructed bound to the *actor's* tenant,
never another's) and the today-window filter, without a live database.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import apps.api._daily_driver_wiring as wiring
from contexts.calendar.domain.meeting import Meeting, MeetingStatus
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

_TENANT_A = "00000000-0000-4000-8000-00000000a001"
_TENANT_B = "00000000-0000-4000-8000-00000000a002"
_DAY = date(2026, 6, 5)


def _actor(tenant_id: str) -> ActorContext:
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=tenant_id, jurisdiction="eu-west", cost_attribution_id=tenant_id
        ),
        actor_id=f"operator-{tenant_id[-1]}",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _meeting(title: str, *, tenant_id: str, when: datetime) -> Meeting:
    return Meeting(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        jurisdiction="eu-west",
        google_event_id=f"evt-{title}",
        status=MeetingStatus.CONFIRMED,
        title=title,
        description=None,
        location=None,
        attendees=(),
        organizer_email=None,
        start_at=when,
        end_at=None,
        start_raw=when.isoformat(),
        end_raw=None,
        source_updated_at=None,
        recurring_event_id=None,
        html_link=None,
        content_hash="h",
        created_at=when,
        updated_at=when,
    )


class _StubStore:
    """Records the tenant it was bound to; serves only that tenant's meetings."""

    instances: list["_StubStore"] = []
    by_tenant: dict[str, tuple[Meeting, ...]] = {}

    def __init__(self, *, per_tenant_sessionmaker_resolver, bound_tenant_id):
        self.bound_tenant_id = str(bound_tenant_id)
        _StubStore.instances.append(self)

    async def list_meetings(self, *, tenant_context, include_cancelled=False):
        # Defence-in-depth shape: the store only ever returns its bound
        # tenant's rows (a foreign tenant's data is structurally unreachable).
        return _StubStore.by_tenant.get(self.bound_tenant_id, ())


def _adapter(monkeypatch, *, domain_tag: str = "work"):
    monkeypatch.setattr(wiring, "PostgresMeetingStore", _StubStore)

    async def _sf(_tenant_context):
        return object()  # an opaque sessionmaker; the stub ignores it

    return wiring.CalendarEventsReaderAdapter(
        session_factory_for_tenant=_sf, domain_tag=domain_tag
    )


def test_reader_binds_store_to_the_actors_tenant(monkeypatch) -> None:
    _StubStore.instances = []
    _StubStore.by_tenant = {
        _TENANT_A: (
            _meeting(
                "A standup",
                tenant_id=_TENANT_A,
                when=datetime(2026, 6, 5, 10, 0, tzinfo=timezone.utc),
            ),
        ),
        _TENANT_B: (
            _meeting(
                "B board",
                tenant_id=_TENANT_B,
                when=datetime(2026, 6, 5, 11, 0, tzinfo=timezone.utc),
            ),
        ),
    }
    adapter = _adapter(monkeypatch)

    a_events = asyncio.run(
        adapter.list_today_events(actor=_actor(_TENANT_A), day_date=_DAY)
    )
    b_events = asyncio.run(
        adapter.list_today_events(actor=_actor(_TENANT_B), day_date=_DAY)
    )

    # Each call bound the store to its own actor's tenant — never the other's.
    assert _StubStore.instances[0].bound_tenant_id == _TENANT_A
    assert _StubStore.instances[1].bound_tenant_id == _TENANT_B
    # And each tenant sees only its own events (the isolation invariant, D24).
    assert [e.title for e in a_events] == ["A standup"]
    assert [e.title for e in b_events] == ["B board"]
    assert all(e.domain == "work" for e in a_events)


def test_today_window_excludes_other_days(monkeypatch) -> None:
    _StubStore.instances = []
    _StubStore.by_tenant = {
        _TENANT_A: (
            _meeting(
                "today",
                tenant_id=_TENANT_A,
                when=datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc),
            ),
            _meeting(
                "yesterday",
                tenant_id=_TENANT_A,
                when=datetime(2026, 6, 4, 9, 0, tzinfo=timezone.utc),
            ),
            _meeting(
                "tomorrow",
                tenant_id=_TENANT_A,
                when=datetime(2026, 6, 6, 9, 0, tzinfo=timezone.utc),
            ),
        )
    }
    adapter = _adapter(monkeypatch)
    events = asyncio.run(
        adapter.list_today_events(actor=_actor(_TENANT_A), day_date=_DAY)
    )
    assert [e.title for e in events] == ["today"]


def test_domain_tag_applied_and_unknown_falls_back(monkeypatch) -> None:
    _StubStore.instances = []
    _StubStore.by_tenant = {
        _TENANT_A: (
            _meeting(
                "1:1",
                tenant_id=_TENANT_A,
                when=datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc),
            ),
        )
    }
    adapter = _adapter(monkeypatch, domain_tag="personal")
    events = asyncio.run(
        adapter.list_today_events(actor=_actor(_TENANT_A), day_date=_DAY)
    )
    assert events[0].domain == "personal"

    adapter2 = _adapter(monkeypatch, domain_tag="rocketship")  # unknown
    events2 = asyncio.run(
        adapter2.list_today_events(actor=_actor(_TENANT_A), day_date=_DAY)
    )
    assert events2[0].domain == "work"  # resolve_calendar_domain default
