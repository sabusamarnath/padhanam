"""Unit tests for the Nango Proxy calendar adapter (D148, D149).

Uses httpx.MockTransport to assert request construction (the verified
headers; the Bearer auth form Nango 0.70.5 requires; the full sync's
show_deleted=true for tombstones; the vendor-reconciliation constraint
that full sync never sends syncToken and incremental sync never sends
timeMin/timeMax/q/orderBy) and response mapping (200 page, 410 ->
SyncTokenExpiredError, auth -> config error, 5xx -> retryable error,
cancelled tombstone).

D149 note on MockTransport's limits: these tests return author-populated
response bodies, so they verify the adapter *parses* a response shape —
they cannot verify what real Google *emits*. The live S55a smoke is the
gate for emit-side vendor contract (it caught that a bounded full sync
returns no nextSyncToken). The incremental + 410 tests below cover the
DORMANT path (no active caller under D149; reactivation trigger in D149).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from contexts.calendar.adapters.outbound.nango.nango_proxy_calendar_adapter import (
    NangoProxyCalendarAdapter,
)
from contexts.calendar.domain.calendar_event import CalendarEventStatus
from contexts.calendar.domain.connection import Connection
from contexts.calendar.domain.errors import (
    CalendarSourceConfigurationError,
    CalendarSourceError,
    SyncTokenExpiredError,
)

_T0 = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
_T1 = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)


def _connection() -> Connection:
    return Connection(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        provider="google_calendar",
        provider_config_key="google-calendar",
        provider_connection_ref="d46195b2-ad85-4d1c-a876-b978b9347ccd",
        created_at=_T0,
        updated_at=_T0,
    )


def _adapter(handler) -> tuple[NangoProxyCalendarAdapter, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(_capture))
    return (
        NangoProxyCalendarAdapter(
            base_url="http://localhost:3003",
            secret_key="sek_test",
            client=client,
        ),
        seen,
    )


_PAGE_BODY = {
    "items": [
        {
            "id": "evt-1",
            "status": "confirmed",
            "summary": "Board sync",
            "description": "Quarterly review",
            "location": "Room 4",
            "start": {"dateTime": "2026-05-12T09:00:00+01:00"},
            "end": {"dateTime": "2026-05-12T10:00:00+01:00"},
            "organizer": {"email": "chair@example.com"},
            "attendees": [
                {
                    "email": "a@example.com",
                    "displayName": "Ada",
                    "responseStatus": "accepted",
                    "organizer": True,
                }
            ],
            "updated": "2026-05-01T08:00:00Z",
            "htmlLink": "https://calendar.google.com/evt-1",
        },
        {"id": "evt-2", "status": "cancelled"},
    ],
    "nextSyncToken": "SYNC_NEXT",
}


def test_full_sync_request_shape_and_parsing() -> None:
    adapter, seen = _adapter(lambda req: httpx.Response(200, json=_PAGE_BODY))
    page = asyncio.run(
        adapter.list_events_full(
            connection=_connection(), time_min=_T0, time_max=_T1
        )
    )

    req = seen[0]
    assert req.url.path == "/proxy/calendar/v3/calendars/primary/events"
    assert req.headers["Authorization"] == "Bearer sek_test"
    assert req.headers["Provider-Config-Key"] == "google-calendar"
    assert req.headers["Connection-Id"] == "d46195b2-ad85-4d1c-a876-b978b9347ccd"
    q = dict(req.url.params)
    assert "timeMin" in q and "timeMax" in q
    assert q["singleEvents"] == "true"
    # D149: the full pull asks for deletions so cancellations tombstone.
    assert q["showDeleted"] == "true"
    # Full sync must NOT carry syncToken or the free-text q (local search).
    assert "syncToken" not in q
    assert "q" not in q

    assert page.next_sync_token == "SYNC_NEXT"
    assert len(page.events) == 2
    first = page.events[0]
    assert first.google_event_id == "evt-1"
    assert first.summary == "Board sync"
    assert first.organizer_email == "chair@example.com"
    assert first.attendees[0].display_name == "Ada"
    # Cancelled event is a tombstone carrying only id + status.
    assert page.events[1].is_tombstone
    assert page.events[1].status is CalendarEventStatus.CANCELLED


def test_proxy_auth_is_bearer_not_basic() -> None:
    # Pin the auth form. Nango 0.70.5 rejects HTTP Basic on the Proxy with
    # a misleading "not a UUID v4" error even for a valid key, so the
    # Bearer form is load-bearing (captures 2026-06-02 [S55a-fix] Finding 3).
    # A regression to Basic must fail here, not at a live smoke.
    adapter, seen = _adapter(lambda req: httpx.Response(200, json=_PAGE_BODY))
    asyncio.run(
        adapter.list_events_full(
            connection=_connection(), time_min=_T0, time_max=_T1
        )
    )
    auth = seen[0].headers["Authorization"]
    assert auth == "Bearer sek_test"
    assert auth.startswith("Bearer ")
    assert not auth.startswith("Basic ")


def test_incremental_sync_sends_only_sync_token() -> None:
    # Dormant path under D149 (no active caller); kept covered for the
    # reactivation trigger named in D149.
    adapter, seen = _adapter(lambda req: httpx.Response(200, json=_PAGE_BODY))
    asyncio.run(
        adapter.list_events_incremental(
            connection=_connection(), sync_token="SYNC_PREV"
        )
    )
    q = dict(seen[0].url.params)
    assert q["syncToken"] == "SYNC_PREV"
    # Incompatible-with-syncToken params must be absent (would 400).
    for forbidden in ("timeMin", "timeMax", "q", "orderBy", "updatedMin"):
        assert forbidden not in q


def test_410_raises_sync_token_expired() -> None:
    # Dormant path under D149 (no active caller); the 410 mapping is kept
    # for the reactivation trigger named in D149.
    adapter, _ = _adapter(lambda req: httpx.Response(410, text="Gone"))
    with pytest.raises(SyncTokenExpiredError):
        asyncio.run(
            adapter.list_events_incremental(
                connection=_connection(), sync_token="STALE"
            )
        )


@pytest.mark.parametrize("code", [400, 401, 403])
def test_auth_and_bad_request_raise_configuration_error(code: int) -> None:
    adapter, _ = _adapter(lambda req: httpx.Response(code, text="nope"))
    with pytest.raises(CalendarSourceConfigurationError):
        asyncio.run(
            adapter.list_events_full(
                connection=_connection(), time_min=_T0, time_max=_T1
            )
        )


def test_5xx_raises_retryable_error() -> None:
    adapter, _ = _adapter(lambda req: httpx.Response(503, text="busy"))
    with pytest.raises(CalendarSourceError):
        asyncio.run(
            adapter.list_events_full(
                connection=_connection(), time_min=_T0, time_max=_T1
            )
        )
