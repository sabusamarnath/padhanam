"""sync_calendar — the trigger-agnostic pull-store-sync pipeline (D148).

A function, not a Protocol: it takes its trigger context as a plain
parameter with one caller today (the poll). It pulls events scoped via
the calendar source port, stores each as a Meeting keyed on the Google
event id (upsert modified, tombstone cancelled), and keeps the store
fresh with self-driven incremental sync tokens — full sync when no token
is stored, incremental otherwise, with a full resync on the 410 path.

Reconciled against the Google events.list constraint that syncToken is
mutually exclusive with timeMin/timeMax/q (the window is set on the full
sync; incremental carries only the token). Indexing the stored Meetings
into the inherited retrieval substrate is layered on in commit 6; this
function reports which events are new-or-content-changed so the indexing
step knows what to re-embed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from contexts.calendar.application.index_meeting import index_meeting
from contexts.calendar.domain.calendar_event import CalendarEvent
from contexts.calendar.domain.errors import (
    NoSuchConnectionError,
    SyncTokenExpiredError,
)
from contexts.calendar.domain.meeting import Meeting, meeting_from_event
from contexts.calendar.domain.sync_trigger import CalendarSyncTrigger
from contexts.calendar.ports.calendar_event_source_port import (
    CalendarEventSourcePort,
)
from contexts.calendar.ports.connection_repository import ConnectionRepository
from contexts.calendar.ports.meeting_index_ports import (
    MeetingEmbeddingPort,
    MeetingGraphIndexPort,
)
from contexts.calendar.ports.meeting_repository import (
    MeetingReader,
    MeetingRepository,
)
from shared_kernel.tenant_context import TenantContext

_MAX_PAGES = 100


@dataclass(frozen=True)
class CalendarSyncResult:
    mode: str  # "full" | "incremental"
    fetched: int
    upserted: int
    tombstoned: int
    changed_event_ids: tuple[str, ...]
    next_sync_token: str | None
    did_full_resync_after_410: bool = False
    indexed: int = 0


async def sync_calendar(
    *,
    tenant_context: TenantContext,
    connection_id: UUID,
    trigger: CalendarSyncTrigger,
    event_source: CalendarEventSourcePort,
    connections: ConnectionRepository,
    meetings: MeetingRepository,
    meeting_reader: MeetingReader,
    embedder: MeetingEmbeddingPort | None = None,
    graph_index: MeetingGraphIndexPort | None = None,
    window_days_past: int = 30,
    window_days_future: int = 90,
    now: datetime | None = None,
) -> CalendarSyncResult:
    """Pull, store, sync, and (when wired) index one calendar connection.

    ``trigger`` is the trigger-agnostic seam: a poll drives it today; a
    future webhook would drive the same function. It is recorded for
    observability and does not change the pull logic. When ``embedder``
    and ``graph_index`` are supplied (the inherited substrate, bridged at
    apps/ wiring), new-or-content-changed Meetings are re-embedded and
    re-indexed after store — a content change re-indexes, not only updates
    the row.
    """
    del trigger  # recorded by the caller; no branch on it today
    now = now or datetime.now(timezone.utc)

    connection = await connections.get_connection(
        tenant_context=tenant_context, connection_id=connection_id
    )
    if connection is None:
        raise NoSuchConnectionError(str(connection_id))

    stored_token = await connections.get_sync_token(
        tenant_context=tenant_context, connection_id=connection_id
    )

    did_full_resync = False
    if stored_token:
        try:
            events, next_token = await _drain_incremental(
                event_source, connection, stored_token
            )
            mode = "incremental"
        except SyncTokenExpiredError:
            # 410: clear the stale token and fall back to a full resync.
            await connections.set_sync_token(
                tenant_context=tenant_context,
                connection_id=connection_id,
                sync_token=None,
            )
            did_full_resync = True
            events, next_token = await _drain_full(
                event_source, connection, now, window_days_past, window_days_future
            )
            mode = "full"
    else:
        events, next_token = await _drain_full(
            event_source, connection, now, window_days_past, window_days_future
        )
        mode = "full"

    upserted = 0
    tombstoned = 0
    changed: list[str] = []
    changed_meetings: list[Meeting] = []
    for event in events:
        if event.is_tombstone:
            await meetings.tombstone_meeting(
                tenant_context=tenant_context,
                google_event_id=event.google_event_id,
                cancelled_at=now,
            )
            tombstoned += 1
            continue

        existing = await meeting_reader.get_by_event_id(
            tenant_context=tenant_context,
            google_event_id=event.google_event_id,
        )
        meeting = meeting_from_event(
            event,
            tenant_id=UUID(tenant_context.tenant_id),
            jurisdiction=tenant_context.jurisdiction,
            meeting_id=existing.id if existing is not None else uuid4(),
            now=now,
            created_at=existing.created_at if existing is not None else None,
        )
        await meetings.upsert_meeting(
            tenant_context=tenant_context, meeting=meeting
        )
        upserted += 1
        if existing is None or existing.content_hash != meeting.content_hash:
            changed.append(event.google_event_id)
            changed_meetings.append(meeting)

    # Index new-or-content-changed Meetings into the inherited substrate
    # when the embedding + graph ports are wired (the survey result: a
    # content change re-embeds and re-indexes, not only updates the row).
    indexed = 0
    if embedder is not None and graph_index is not None:
        for meeting in changed_meetings:
            await index_meeting(
                tenant_context=tenant_context,
                meeting=meeting,
                embedder=embedder,
                graph_index=graph_index,
                meetings=meetings,
            )
            indexed += 1

    # Persist the next sync token for the following incremental pull. A
    # sync run that returns no token (shouldn't happen on a completed run)
    # leaves the stored token untouched.
    if next_token is not None:
        await connections.set_sync_token(
            tenant_context=tenant_context,
            connection_id=connection_id,
            sync_token=next_token,
        )

    return CalendarSyncResult(
        mode=mode,
        fetched=len(events),
        upserted=upserted,
        tombstoned=tombstoned,
        changed_event_ids=tuple(changed),
        next_sync_token=next_token,
        did_full_resync_after_410=did_full_resync,
        indexed=indexed,
    )


async def _drain_full(
    event_source: CalendarEventSourcePort,
    connection,
    now: datetime,
    window_days_past: int,
    window_days_future: int,
) -> tuple[list[CalendarEvent], str | None]:
    time_min = now - timedelta(days=window_days_past)
    time_max = now + timedelta(days=window_days_future)
    collected: list[CalendarEvent] = []
    page_token: str | None = None
    next_sync_token: str | None = None
    for _ in range(_MAX_PAGES):
        page = await event_source.list_events_full(
            connection=connection,
            time_min=time_min,
            time_max=time_max,
            page_token=page_token,
        )
        collected.extend(page.events)
        next_sync_token = page.next_sync_token or next_sync_token
        if not page.next_page_token:
            break
        page_token = page.next_page_token
    return collected, next_sync_token


async def _drain_incremental(
    event_source: CalendarEventSourcePort,
    connection,
    sync_token: str,
) -> tuple[list[CalendarEvent], str | None]:
    collected: list[CalendarEvent] = []
    page_token: str | None = None
    next_sync_token: str | None = None
    for _ in range(_MAX_PAGES):
        page = await event_source.list_events_incremental(
            connection=connection,
            sync_token=sync_token,
            page_token=page_token,
        )
        collected.extend(page.events)
        next_sync_token = page.next_sync_token or next_sync_token
        if not page.next_page_token:
            break
        page_token = page.next_page_token
    return collected, next_sync_token


__all__ = ["CalendarSyncResult", "sync_calendar"]
