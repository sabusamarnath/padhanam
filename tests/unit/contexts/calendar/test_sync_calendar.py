"""Unit tests for the trigger-agnostic sync_calendar pipeline (D148, D149).

The active path is a scoped full pull on every refresh (D149): no sync
token is read or written, an absent ``next_sync_token`` is expected, and
cancellations arrive as ``status=cancelled`` tombstones via the full
pull's ``show_deleted=True``. In-memory fakes for the four ports exercise
the full-pull store loop, content-change detection, id/created_at reuse,
tombstoning, the absent-token case, and page-draining-before-tombstone —
without live infrastructure. The incremental syncToken/410 machinery is
covered as a dormant path in ``test_nango_proxy_calendar_adapter.py``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.calendar.application.sync_calendar import sync_calendar
from contexts.calendar.domain.calendar_event import (
    CalendarEvent,
    CalendarEventPage,
    CalendarEventStatus,
)
from contexts.calendar.domain.connection import Connection
from contexts.calendar.domain.errors import NoSuchConnectionError
from contexts.calendar.domain.meeting import meeting_from_event
from contexts.calendar.domain.sync_trigger import CalendarSyncTrigger
from shared_kernel.tenant_context import TenantContext

_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=timezone.utc)
_TENANT_ID = "11111111-1111-1111-1111-111111111111"
_CONN_ID = UUID("22222222-2222-2222-2222-222222222222")


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_ID, jurisdiction="eu-west", cost_attribution_id="cost"
    )


def _connection() -> Connection:
    return Connection(
        id=_CONN_ID,
        tenant_id=UUID(_TENANT_ID),
        jurisdiction="eu-west",
        provider="google_calendar",
        provider_config_key="google-calendar",
        provider_connection_ref="d46195b2",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _event(event_id: str, *, summary: str = "Sync", cancelled: bool = False) -> CalendarEvent:
    return CalendarEvent(
        google_event_id=event_id,
        status=(
            CalendarEventStatus.CANCELLED
            if cancelled
            else CalendarEventStatus.CONFIRMED
        ),
        summary=None if cancelled else summary,
        start="2026-05-29T09:00:00+00:00" if not cancelled else None,
    )


class FakeEventSource:
    def __init__(self, *, full_pages: list[CalendarEventPage] | None = None) -> None:
        self._full = list(full_pages or [])
        self.full_calls = 0
        self.incremental_calls = 0
        self.last_show_deleted: bool | None = None

    async def list_events_full(self, *, show_deleted: bool = True, **_kwargs) -> CalendarEventPage:
        self.full_calls += 1
        self.last_show_deleted = show_deleted
        return self._full.pop(0) if self._full else CalendarEventPage(events=())

    async def list_events_incremental(self, **_kwargs) -> CalendarEventPage:  # pragma: no cover
        # Dormant under D149 — the active pipeline never calls this.
        self.incremental_calls += 1
        return CalendarEventPage(events=())


class FakeConnectionRepo:
    def __init__(self, connection: Connection | None, token: str | None = None) -> None:
        self._connection = connection
        self.token = token
        self.get_token_calls = 0
        self.set_token_calls = 0

    async def save_connection(self, **_kwargs) -> None:  # pragma: no cover
        pass

    async def get_connection(self, *, tenant_context, connection_id) -> Connection | None:
        return self._connection

    async def get_sync_token(self, *, tenant_context, connection_id) -> str | None:
        # Dormant under D149; the active path must not call this.
        self.get_token_calls += 1
        return self.token

    async def set_sync_token(self, *, tenant_context, connection_id, sync_token) -> None:
        # Dormant under D149; the active path must not call this.
        self.set_token_calls += 1
        self.token = sync_token


class FakeMeetingStore:
    def __init__(self) -> None:
        self.by_event: dict[str, object] = {}
        self.tombstoned: list[str] = []
        self.embeddings: dict[str, list[float]] = {}
        # D176: record the calendar_id every write/lookup is scoped by.
        self.tombstone_calendar_ids: list[str] = []
        self.get_calendar_ids: list[str | None] = []

    async def upsert_meeting(self, *, tenant_context, meeting) -> None:
        self.by_event[meeting.google_event_id] = meeting

    async def tombstone_meeting(
        self, *, tenant_context, calendar_id, google_event_id, cancelled_at
    ) -> None:
        self.tombstoned.append(google_event_id)
        self.tombstone_calendar_ids.append(calendar_id)
        self.by_event.pop(google_event_id, None)

    async def set_embedding(
        self, *, tenant_context, calendar_id, google_event_id, vector
    ) -> None:
        self.embeddings[google_event_id] = list(vector)

    async def get_by_event_id(
        self, *, tenant_context, google_event_id, calendar_id=None
    ):
        self.get_calendar_ids.append(calendar_id)
        return self.by_event.get(google_event_id)

    async def list_meetings(self, *, tenant_context, include_cancelled=False):  # pragma: no cover
        return tuple(self.by_event.values())


def _run(source, conns, store, **kwargs):
    return asyncio.run(
        sync_calendar(
            tenant_context=_ctx(),
            connection_id=_CONN_ID,
            trigger=CalendarSyncTrigger.POLL,
            event_source=source,
            connections=conns,
            meetings=store,
            meeting_reader=store,
            now=_NOW,
            **kwargs,
        )
    )


def test_full_pull_stores_events_and_writes_no_sync_token() -> None:
    # A bounded full sync returns no nextSyncToken; the active path must
    # not depend on one and must not write connections.sync_token (D149).
    source = FakeEventSource(
        full_pages=[
            CalendarEventPage(events=(_event("a"), _event("b")), next_sync_token=None)
        ]
    )
    conns = FakeConnectionRepo(_connection(), token=None)
    store = FakeMeetingStore()
    result = _run(source, conns, store)

    assert result.mode == "full"
    assert result.upserted == 2
    assert set(result.changed_event_ids) == {"a", "b"}
    assert source.full_calls == 1
    # The full pull asks for deletions so cancellations tombstone.
    assert source.last_show_deleted is True
    # No sync-token machinery touched on the active path.
    assert conns.set_token_calls == 0
    assert conns.get_token_calls == 0
    assert conns.token is None
    assert source.incremental_calls == 0


def test_absent_token_full_pull_does_not_raise() -> None:
    # The defining D149 case: a completed full pull with no token is the
    # normal, expected outcome — never an error.
    source = FakeEventSource(
        full_pages=[CalendarEventPage(events=(_event("a"),), next_sync_token=None)]
    )
    conns = FakeConnectionRepo(_connection(), token=None)
    store = FakeMeetingStore()
    result = _run(source, conns, store)  # must not raise

    assert result.mode == "full"
    assert result.fetched == 1
    assert conns.set_token_calls == 0


def test_cancelled_event_is_tombstoned_via_full_pull() -> None:
    source = FakeEventSource(
        full_pages=[
            CalendarEventPage(
                events=(_event("a"), _event("b", cancelled=True)),
                next_sync_token=None,
            )
        ]
    )
    conns = FakeConnectionRepo(_connection(), token=None)
    store = FakeMeetingStore()
    result = _run(source, conns, store)

    assert result.tombstoned == 1
    assert "b" in store.tombstoned
    assert "a" in store.by_event


def test_full_pull_drains_all_pages_before_tombstone_pass() -> None:
    # Page 1 carries a live event and a next_page_token; page 2 carries a
    # cancellation. The store loop runs only after both pages are drained,
    # so the cancellation on page 2 still tombstones and no live event is
    # processed against a partial window.
    source = FakeEventSource(
        full_pages=[
            CalendarEventPage(events=(_event("a"),), next_page_token="P2"),
            CalendarEventPage(events=(_event("b", cancelled=True),), next_page_token=None),
        ]
    )
    conns = FakeConnectionRepo(_connection(), token=None)
    store = FakeMeetingStore()
    result = _run(source, conns, store)

    assert source.full_calls == 2
    assert result.fetched == 2
    assert result.upserted == 1
    assert "a" in store.by_event
    assert result.tombstoned == 1
    assert "b" in store.tombstoned


def test_unchanged_content_not_marked_changed_and_id_reused() -> None:
    store = FakeMeetingStore()
    # Seed an existing meeting for event "a".
    existing = meeting_from_event(
        _event("a", summary="Sync"),
        tenant_id=UUID(_TENANT_ID),
        jurisdiction="eu-west",
        meeting_id=uuid4(),
        now=_NOW,
    )
    store.by_event["a"] = existing

    source = FakeEventSource(
        full_pages=[
            CalendarEventPage(events=(_event("a", summary="Sync"),), next_sync_token=None)
        ]
    )
    conns = FakeConnectionRepo(_connection(), token=None)
    result = _run(source, conns, store)

    # Same content -> not flagged for re-index; id + created_at preserved.
    assert "a" not in result.changed_event_ids
    assert store.by_event["a"].id == existing.id
    assert store.by_event["a"].created_at == existing.created_at


def test_missing_connection_raises() -> None:
    source = FakeEventSource(full_pages=[])
    conns = FakeConnectionRepo(None)
    store = FakeMeetingStore()
    with pytest.raises(NoSuchConnectionError):
        _run(source, conns, store)


def test_sync_stamps_and_scopes_writes_by_calendar_id() -> None:
    """D176: the pull stamps the connection id as calendar_id on each Meeting
    and scopes its change-detection get and its tombstone by it, so a pull of
    one calendar never reads or writes another calendar's rows."""
    store = FakeMeetingStore()
    source = FakeEventSource(
        full_pages=[
            CalendarEventPage(
                events=(
                    _event("live", summary="Standup"),
                    _event("gone", cancelled=True),
                ),
                next_sync_token=None,
            )
        ]
    )
    conns = FakeConnectionRepo(_connection(), token=None)
    _run(source, conns, store)

    # The stamped calendar_id is the connection id (the scope key).
    assert store.by_event["live"].calendar_id == str(_CONN_ID)
    # The change-detection get and the tombstone were scoped by it.
    assert store.get_calendar_ids == [str(_CONN_ID)]
    assert store.tombstone_calendar_ids == [str(_CONN_ID)]
