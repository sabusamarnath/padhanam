"""sync_calendar — the trigger-agnostic pull-store-sync pipeline (D148, D149).

A function, not a Protocol: it takes its trigger context as a plain
parameter with one caller today (the poll). It pulls events scoped via
the calendar source port, stores each as a Meeting keyed on the Google
event id (upsert modified, tombstone cancelled), and reports which
events are new-or-content-changed so the indexing step knows what to
re-embed.

Sync mechanism (D149, superseding D148's receive-side sync clause). The
active path is a **scoped full pull on every refresh**: it carries
``timeMin``/``timeMax`` plus ``showDeleted=true`` so cancellations come
back as ``status=cancelled`` tombstones, and depends on no sync token.
The live S55a smoke established that Google's ``events.list`` returns
``nextSyncToken`` only on an *unbounded* full sync, so a bounded request
never yields a token to bootstrap incremental sync. The incremental
machinery (``CalendarEventSourcePort.list_events_incremental``, the
410-to-``SyncTokenExpiredError`` mapping, ``connections.{get,set}_sync_token``
and the ``connections.sync_token`` column) is built and unit-tested but
**dormant** — unreferenced by this active path. Reactivation trigger
(Phase 2-B multi-user scale, or single-calendar volume breaching the
D122 refresh-before-answer budget) is named in D149.

Indexing the stored Meetings into the inherited retrieval substrate is
layered on when the embedding + graph ports are supplied (bridged at the
apps/ composition root, S55b).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from contexts.calendar.application.index_meeting import index_meeting
from contexts.calendar.domain.calendar_event import CalendarEvent
from contexts.calendar.domain.errors import NoSuchConnectionError
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
    mode: str  # "full" — the only active mode under D149's scoped full-pull
    fetched: int
    upserted: int
    tombstoned: int
    changed_event_ids: tuple[str, ...]
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
    """Pull, store, and (when wired) index one calendar connection.

    ``trigger`` is the trigger-agnostic seam: a poll drives it today; a
    future webhook would drive the same function. It is recorded for
    observability and does not change the pull logic. When ``embedder``
    and ``graph_index`` are supplied (the inherited substrate, bridged at
    apps/ wiring), new-or-content-changed Meetings are re-embedded and
    re-indexed after store — a content change re-indexes, not only updates
    the row.

    The pull is a scoped full sync on every call (D149): no stored sync
    token is read or written; an absent ``next_sync_token`` is expected,
    not an error. Cancelled events arrive as ``status=cancelled``
    tombstones via ``showDeleted=true`` on the full pull.
    """
    del trigger  # recorded by the caller; no branch on it today
    now = now or datetime.now(timezone.utc)

    connection = await connections.get_connection(
        tenant_context=tenant_context, connection_id=connection_id
    )
    if connection is None:
        raise NoSuchConnectionError(str(connection_id))

    # Scoped full pull (D149). Drains every page before the store loop
    # runs, so a tombstone pass never sees a partially-fetched window.
    events = await _drain_full(
        event_source, connection, now, window_days_past, window_days_future
    )

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

    return CalendarSyncResult(
        mode="full",
        fetched=len(events),
        upserted=upserted,
        tombstoned=tombstoned,
        changed_event_ids=tuple(changed),
        indexed=indexed,
    )


async def _drain_full(
    event_source: CalendarEventSourcePort,
    connection,
    now: datetime,
    window_days_past: int,
    window_days_future: int,
) -> list[CalendarEvent]:
    """Drain every page of a scoped full sync into one list.

    Carries ``show_deleted=True`` so cancelled events return as tombstones
    (D149 deletion detection). Returns no sync token: a bounded full sync
    never emits one, and the active path does not need it.
    """
    time_min = now - timedelta(days=window_days_past)
    time_max = now + timedelta(days=window_days_future)
    collected: list[CalendarEvent] = []
    page_token: str | None = None
    for _ in range(_MAX_PAGES):
        page = await event_source.list_events_full(
            connection=connection,
            time_min=time_min,
            time_max=time_max,
            page_token=page_token,
            show_deleted=True,
        )
        collected.extend(page.events)
        if not page.next_page_token:
            break
        page_token = page.next_page_token
    return collected


__all__ = ["CalendarSyncResult", "sync_calendar"]
