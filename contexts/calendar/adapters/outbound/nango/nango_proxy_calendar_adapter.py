"""NangoProxyCalendarAdapter — the single CalendarEventSourcePort adapter (D148).

Fetches Google Calendar events through self-hosted Nango's Proxy over
HTTP, against the five verified handles from the Nango provisioning
session. The only place in the calendar context that speaks Google's
wire format or Nango Proxy's headers; everything Google- or Nango-
specific lives here (no-vendor-SDK-in-domain).

Reconciled against the current Google Calendar API ``events.list`` docs
(2026-05-28): ``syncToken`` is mutually exclusive with
``timeMin``/``timeMax``/``q``/``orderBy``/``updatedMin`` (400 if mixed),
so full and incremental sync are separate request shapes; an expired
sync token returns ``410 GONE`` (→ SyncTokenExpiredError → full resync);
cancelled events carry ``status: "cancelled"`` and are always present in
incremental results. The sync path never sends ``q`` — search runs
locally over the substrate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from contexts.calendar.domain.calendar_event import (
    CalendarEvent,
    CalendarEventPage,
    CalendarEventStatus,
    EventAttendee,
)
from contexts.calendar.domain.connection import Connection
from contexts.calendar.domain.errors import (
    CalendarSourceConfigurationError,
    CalendarSourceError,
    SyncTokenExpiredError,
)

_DEFAULT_MAX_RESULTS = 250
_DEFAULT_TIMEOUT = 30.0


def _rfc3339(value: datetime) -> str:
    """RFC3339 with a mandatory offset, as the Calendar API requires."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


class NangoProxyCalendarAdapter:
    """Single CalendarEventSourcePort adapter over Nango Proxy."""

    def __init__(
        self,
        *,
        base_url: str,
        secret_key: str,
        client: httpx.AsyncClient | None = None,
        max_results: int = _DEFAULT_MAX_RESULTS,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret_key = secret_key
        self._client = client
        self._owns_client = client is None
        self._max_results = max_results
        self._timeout = timeout

    async def list_events_full(
        self,
        *,
        connection: Connection,
        time_min: datetime,
        time_max: datetime,
        page_token: str | None = None,
        calendar_id: str = "primary",
        single_events: bool = True,
    ) -> CalendarEventPage:
        params: dict[str, str] = {
            "timeMin": _rfc3339(time_min),
            "timeMax": _rfc3339(time_max),
            "singleEvents": "true" if single_events else "false",
            "maxResults": str(self._max_results),
        }
        if single_events:
            # orderBy=startTime is only valid with singleEvents=true and is
            # incompatible with syncToken — safe only on the full sync.
            params["orderBy"] = "startTime"
        if page_token:
            params["pageToken"] = page_token
        return await self._list(connection, calendar_id, params)

    async def list_events_incremental(
        self,
        *,
        connection: Connection,
        sync_token: str,
        page_token: str | None = None,
        calendar_id: str = "primary",
        single_events: bool = True,
    ) -> CalendarEventPage:
        # syncToken only (plus pagination + a consistent singleEvents). No
        # timeMin/timeMax/q/orderBy — they would 400 against a syncToken.
        params: dict[str, str] = {
            "syncToken": sync_token,
            "singleEvents": "true" if single_events else "false",
            "maxResults": str(self._max_results),
        }
        if page_token:
            params["pageToken"] = page_token
        return await self._list(connection, calendar_id, params)

    async def _list(
        self,
        connection: Connection,
        calendar_id: str,
        params: dict[str, str],
    ) -> CalendarEventPage:
        url = f"{self._base_url}/proxy/calendar/v3/calendars/{calendar_id}/events"
        headers = {
            "Authorization": f"Bearer {self._secret_key}",
            "Provider-Config-Key": connection.provider_config_key,
            "Connection-Id": connection.provider_connection_ref,
        }
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:  # network/timeout — retryable
            raise CalendarSourceError(
                f"calendar proxy request failed: {exc}"
            ) from exc
        finally:
            if self._owns_client:
                await client.aclose()

        return self._handle_response(response)

    @staticmethod
    def _handle_response(response: httpx.Response) -> CalendarEventPage:
        status = response.status_code
        if status == 200:
            return _parse_page(response.json())
        if status == 410:
            raise SyncTokenExpiredError(
                "calendar sync token expired (410); full resync required"
            )
        if status in (400, 401, 403):
            raise CalendarSourceConfigurationError(
                f"calendar proxy returned {status}: {response.text[:500]}"
            )
        # 5xx and anything else: treat as transient/retryable.
        raise CalendarSourceError(
            f"calendar proxy returned {status}: {response.text[:500]}"
        )


def _parse_page(body: dict[str, Any]) -> CalendarEventPage:
    items = body.get("items", []) or []
    events = tuple(_parse_event(item) for item in items)
    return CalendarEventPage(
        events=events,
        next_page_token=body.get("nextPageToken"),
        next_sync_token=body.get("nextSyncToken"),
    )


def _parse_event(item: dict[str, Any]) -> CalendarEvent:
    raw_status = (item.get("status") or "confirmed").lower()
    try:
        status = CalendarEventStatus(raw_status)
    except ValueError:
        status = CalendarEventStatus.CONFIRMED

    organizer = item.get("organizer") or {}
    attendees = tuple(
        EventAttendee(
            email=att.get("email"),
            display_name=att.get("displayName"),
            response_status=att.get("responseStatus"),
            organizer=bool(att.get("organizer", False)),
        )
        for att in (item.get("attendees") or [])
    )
    start = item.get("start") or {}
    end = item.get("end") or {}
    return CalendarEvent(
        google_event_id=item["id"],
        status=status,
        summary=item.get("summary"),
        description=item.get("description"),
        location=item.get("location"),
        start=start.get("dateTime") or start.get("date"),
        end=end.get("dateTime") or end.get("date"),
        attendees=attendees,
        organizer_email=organizer.get("email"),
        updated=item.get("updated"),
        html_link=item.get("htmlLink"),
        recurring_event_id=item.get("recurringEventId"),
    )
