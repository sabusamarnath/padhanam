"""Unit tests for Meeting indexing per the substrate-inheritance survey (D148).

Covers the structured Meeting->graph mapping, the index_meeting
orchestration over fake inherited ports, and sync_calendar's indexing step
wiring (changed Meetings embedded + graph-indexed; the embedding stored on
the calendar-owned row).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.calendar.application.index_meeting import index_meeting
from contexts.calendar.application.sync_calendar import sync_calendar
from contexts.calendar.domain.calendar_event import (
    CalendarEvent,
    CalendarEventPage,
    CalendarEventStatus,
)
from contexts.calendar.domain.connection import Connection
from contexts.calendar.domain.meeting import meeting_from_event
from contexts.calendar.domain.meeting_graph import (
    ENTITY_MEETING,
    ENTITY_PERSON,
    ENTITY_PLACE,
    REL_LOCATED_AT,
    meeting_to_graph,
)
from contexts.calendar.domain.sync_trigger import CalendarSyncTrigger
from shared_kernel.tenant_context import TenantContext

_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=timezone.utc)
_TENANT_ID = "11111111-1111-1111-1111-111111111111"
_CONN_ID = UUID("22222222-2222-2222-2222-222222222222")


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_ID, jurisdiction="eu-west", cost_attribution_id="cost"
    )


def _meeting(summary: str = "Board sync", location: str | None = "Room 4"):
    event = CalendarEvent(
        google_event_id="evt-1",
        status=CalendarEventStatus.CONFIRMED,
        summary=summary,
        location=location,
        organizer_email="chair@example.com",
        start="2026-05-29T09:00:00+00:00",
    )
    return meeting_from_event(
        event,
        tenant_id=UUID(_TENANT_ID),
        jurisdiction="eu-west",
        meeting_id=uuid4(),
        now=_NOW,
    )


def test_meeting_to_graph_maps_people_and_place() -> None:
    meeting = _meeting()
    entities, relationships = meeting_to_graph(meeting)
    types = {e.entity_type for e in entities}
    assert ENTITY_MEETING in types
    assert ENTITY_PERSON in types  # organizer
    assert ENTITY_PLACE in types  # location
    assert any(r.relationship_type == REL_LOCATED_AT for r in relationships)


def test_cancelled_meeting_yields_no_graph() -> None:
    from contexts.calendar.domain.meeting import Meeting, MeetingStatus

    cancelled = Meeting(
        id=uuid4(),
        tenant_id=UUID(_TENANT_ID),
        jurisdiction="eu",
        google_event_id="evt-x",
        status=MeetingStatus.CANCELLED,
        title=None,
        description=None,
        location=None,
        attendees=(),
        organizer_email=None,
        start_at=None,
        end_at=None,
        start_raw=None,
        end_raw=None,
        source_updated_at=None,
        recurring_event_id=None,
        html_link=None,
        content_hash=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert meeting_to_graph(cancelled) == ((), ())


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def embed(self, *, text: str, tenant_context):
        self.calls.append(text)
        return [0.1, 0.2, 0.3]


class FakeGraphIndex:
    def __init__(self) -> None:
        self.indexed: list[tuple] = []

    async def index_meeting(self, *, tenant_context, entities, relationships):
        self.indexed.append((tuple(entities), tuple(relationships)))


class FakeMeetingRepo:
    def __init__(self) -> None:
        self.embeddings: dict[str, list[float]] = {}

    async def upsert_meeting(self, *, tenant_context, meeting) -> None:  # pragma: no cover
        pass

    async def tombstone_meeting(self, **_kwargs) -> None:  # pragma: no cover
        pass

    async def set_embedding(
        self, *, tenant_context, calendar_id, google_event_id, vector
    ) -> None:
        self.embeddings[google_event_id] = list(vector)


def test_index_meeting_embeds_and_graph_indexes() -> None:
    embedder, graph, repo = FakeEmbedder(), FakeGraphIndex(), FakeMeetingRepo()
    meeting = _meeting()
    asyncio.run(
        index_meeting(
            tenant_context=_ctx(),
            meeting=meeting,
            embedder=embedder,
            graph_index=graph,
            meetings=repo,
        )
    )
    assert embedder.calls and "Title: Board sync" in embedder.calls[0]
    assert repo.embeddings["evt-1"] == [0.1, 0.2, 0.3]
    assert graph.indexed and len(graph.indexed[0][0]) >= 1


# --- sync_calendar indexing-step wiring -----------------------------------


class _FakeSource:
    def __init__(self, page: CalendarEventPage) -> None:
        self._page = page

    async def list_events_full(self, **_kwargs) -> CalendarEventPage:
        return self._page

    async def list_events_incremental(self, **_kwargs) -> CalendarEventPage:  # pragma: no cover
        return CalendarEventPage(events=())


class _FakeConns:
    def __init__(self) -> None:
        self.token = None

    async def get_connection(self, **_kwargs):
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

    async def get_sync_token(self, **_kwargs):
        return None

    async def set_sync_token(self, *, tenant_context, connection_id, sync_token):
        self.token = sync_token

    async def save_connection(self, **_kwargs):  # pragma: no cover
        pass


class _FakeStore(FakeMeetingRepo):
    def __init__(self) -> None:
        super().__init__()
        self.rows: dict[str, object] = {}

    async def upsert_meeting(self, *, tenant_context, meeting) -> None:
        self.rows[meeting.google_event_id] = meeting

    async def get_by_event_id(
        self, *, tenant_context, google_event_id, calendar_id=None
    ):
        return self.rows.get(google_event_id)

    async def list_meetings(self, **_kwargs):  # pragma: no cover
        return tuple(self.rows.values())


def test_sync_indexes_changed_meetings_when_ports_wired() -> None:
    page = CalendarEventPage(
        events=(
            CalendarEvent(
                google_event_id="evt-1",
                status=CalendarEventStatus.CONFIRMED,
                summary="Board sync",
                organizer_email="chair@example.com",
                start="2026-05-29T09:00:00+00:00",
            ),
        ),
        next_sync_token="TOK",
    )
    embedder, graph, store, conns = (
        FakeEmbedder(),
        FakeGraphIndex(),
        _FakeStore(),
        _FakeConns(),
    )
    result = asyncio.run(
        sync_calendar(
            tenant_context=_ctx(),
            connection_id=_CONN_ID,
            trigger=CalendarSyncTrigger.POLL,
            event_source=_FakeSource(page),
            connections=conns,
            meetings=store,
            meeting_reader=store,
            embedder=embedder,
            graph_index=graph,
            now=_NOW,
        )
    )
    assert result.indexed == 1
    assert store.embeddings["evt-1"] == [0.1, 0.2, 0.3]
    assert len(graph.indexed) == 1


def test_sync_without_ports_does_not_index() -> None:
    page = CalendarEventPage(
        events=(
            CalendarEvent(
                google_event_id="evt-1",
                status=CalendarEventStatus.CONFIRMED,
                summary="Board sync",
                start="2026-05-29T09:00:00+00:00",
            ),
        ),
        next_sync_token="TOK",
    )
    store, conns = _FakeStore(), _FakeConns()
    result = asyncio.run(
        sync_calendar(
            tenant_context=_ctx(),
            connection_id=_CONN_ID,
            trigger=CalendarSyncTrigger.POLL,
            event_source=_FakeSource(page),
            connections=conns,
            meetings=store,
            meeting_reader=store,
            now=_NOW,
        )
    )
    assert result.indexed == 0
    assert store.embeddings == {}
