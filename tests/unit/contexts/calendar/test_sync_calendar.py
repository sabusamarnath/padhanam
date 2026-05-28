"""Unit tests for the trigger-agnostic sync_calendar pipeline (D148).

In-memory fakes for the four ports exercise full sync, incremental sync,
the 410 -> full-resync path, tombstoning, content-change detection, and
id/created_at reuse on update — without live infrastructure.
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
from contexts.calendar.domain.errors import (
    NoSuchConnectionError,
    SyncTokenExpiredError,
)
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
    def __init__(
        self,
        *,
        full_pages: list[CalendarEventPage] | None = None,
        incremental_pages: list[CalendarEventPage] | None = None,
        raise_410_on_incremental: bool = False,
    ) -> None:
        self._full = list(full_pages or [])
        self._incremental = list(incremental_pages or [])
        self._raise_410 = raise_410_on_incremental
        self.full_calls = 0
        self.incremental_calls = 0

    async def list_events_full(self, **_kwargs) -> CalendarEventPage:
        self.full_calls += 1
        return self._full.pop(0) if self._full else CalendarEventPage(events=())

    async def list_events_incremental(self, **_kwargs) -> CalendarEventPage:
        self.incremental_calls += 1
        if self._raise_410:
            raise SyncTokenExpiredError("410")
        return (
            self._incremental.pop(0)
            if self._incremental
            else CalendarEventPage(events=())
        )


class FakeConnectionRepo:
    def __init__(self, connection: Connection | None, token: str | None = None) -> None:
        self._connection = connection
        self.token = token

    async def save_connection(self, **_kwargs) -> None:  # pragma: no cover
        pass

    async def get_connection(self, *, tenant_context, connection_id) -> Connection | None:
        return self._connection

    async def get_sync_token(self, *, tenant_context, connection_id) -> str | None:
        return self.token

    async def set_sync_token(self, *, tenant_context, connection_id, sync_token) -> None:
        self.token = sync_token


class FakeMeetingStore:
    def __init__(self) -> None:
        self.by_event: dict[str, object] = {}
        self.tombstoned: list[str] = []
        self.embeddings: dict[str, list[float]] = {}

    async def upsert_meeting(self, *, tenant_context, meeting) -> None:
        self.by_event[meeting.google_event_id] = meeting

    async def tombstone_meeting(self, *, tenant_context, google_event_id, cancelled_at) -> None:
        self.tombstoned.append(google_event_id)
        self.by_event.pop(google_event_id, None)

    async def set_embedding(self, *, tenant_context, google_event_id, vector) -> None:
        self.embeddings[google_event_id] = list(vector)

    async def get_by_event_id(self, *, tenant_context, google_event_id):
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


def test_full_sync_stores_events_and_persists_sync_token() -> None:
    source = FakeEventSource(
        full_pages=[
            CalendarEventPage(
                events=(_event("a"), _event("b")), next_sync_token="TOK1"
            )
        ]
    )
    conns = FakeConnectionRepo(_connection(), token=None)
    store = FakeMeetingStore()
    result = _run(source, conns, store)

    assert result.mode == "full"
    assert result.upserted == 2
    assert set(result.changed_event_ids) == {"a", "b"}
    assert conns.token == "TOK1"
    assert source.full_calls == 1


def test_incremental_sync_uses_stored_token() -> None:
    source = FakeEventSource(
        incremental_pages=[
            CalendarEventPage(events=(_event("a", summary="Updated"),), next_sync_token="TOK2")
        ]
    )
    conns = FakeConnectionRepo(_connection(), token="TOK1")
    store = FakeMeetingStore()
    result = _run(source, conns, store)

    assert result.mode == "incremental"
    assert source.incremental_calls == 1
    assert source.full_calls == 0
    assert conns.token == "TOK2"


def test_410_triggers_full_resync() -> None:
    source = FakeEventSource(
        raise_410_on_incremental=True,
        full_pages=[CalendarEventPage(events=(_event("a"),), next_sync_token="FRESH")],
    )
    conns = FakeConnectionRepo(_connection(), token="STALE")
    store = FakeMeetingStore()
    result = _run(source, conns, store)

    assert result.did_full_resync_after_410 is True
    assert result.mode == "full"
    assert conns.token == "FRESH"
    assert source.full_calls == 1


def test_cancelled_event_is_tombstoned() -> None:
    source = FakeEventSource(
        full_pages=[
            CalendarEventPage(
                events=(_event("a"), _event("b", cancelled=True)),
                next_sync_token="TOK",
            )
        ]
    )
    conns = FakeConnectionRepo(_connection(), token=None)
    store = FakeMeetingStore()
    result = _run(source, conns, store)

    assert result.tombstoned == 1
    assert "b" in store.tombstoned
    assert "a" in store.by_event


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
        incremental_pages=[
            CalendarEventPage(events=(_event("a", summary="Sync"),), next_sync_token="T")
        ]
    )
    conns = FakeConnectionRepo(_connection(), token="OLD")
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
