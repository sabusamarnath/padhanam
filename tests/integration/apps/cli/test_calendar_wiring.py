"""Calendar composition-root wiring tests (D146, D148, D150, P15, S55b-1).

Exercises the apps bridges with doubles (no live Nango / Ollama / Neo4j):
the MeetingEmbedderBridge over a fake ChunkEmbedder, the
MeetingGraphIndexBridge mapping calendar DTOs to ingestion Entity/
Relationship over a fake GraphRepository, and the CalendarRefreshAdapter
driving the D149 sync_calendar pull-store-index end to end — plus the
D150 failure-mapping to CalendarRefreshError.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from apps.cli._calendar import (
    CalendarRefreshAdapter,
    MeetingEmbedderBridge,
    MeetingGraphIndexBridge,
)
from contexts.calendar.domain.calendar_event import (
    CalendarEvent,
    CalendarEventPage,
    CalendarEventStatus,
)
from contexts.calendar.domain.connection import Connection
from contexts.calendar.domain.errors import CalendarSourceError
from contexts.calendar.domain.meeting_graph import (
    MeetingGraphEntity,
    MeetingGraphRelationship,
)
from contexts.calendar_conversation.application.ports.calendar_refresh import (
    CalendarRefreshError,
)
from contexts.ingestion.domain.embedding_task import EmbeddingTask
from shared_kernel import TenantContext

_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
_TENANT = "00000000-0000-4000-8000-00000000a001"
_CONN = UUID("22222222-2222-2222-2222-222222222222")


def _ctx() -> TenantContext:
    return TenantContext(tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT)


# --------------------------------------------------------- embedder bridge


class _FakeChunkEmbedder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, EmbeddingTask]] = []

    async def embed(self, chunks, tenant_context, task):  # pragma: no cover
        raise AssertionError("the bridge uses embed_query, not embed")

    async def embed_query(self, query, tenant_context, task):
        self.calls.append((query, task))
        return [0.5] * 768


def test_embedder_bridge_uses_embed_query_with_document_task() -> None:
    embedder = _FakeChunkEmbedder()
    bridge = MeetingEmbedderBridge(chunk_embedder=embedder)
    vector = asyncio.run(bridge.embed(text="Title: Board sync", tenant_context=_ctx()))
    assert list(vector) == [0.5] * 768
    assert embedder.calls == [("Title: Board sync", EmbeddingTask.DOCUMENT)]


# --------------------------------------------------------- graph bridge


class _FakeGraphRepository:
    def __init__(self) -> None:
        self.entities: list[Any] = []
        self.relationships: list[Any] = []

    async def merge_entities(self, entities, tenant_context) -> None:
        self.entities.extend(entities)

    async def merge_relationships(self, relationships, tenant_context) -> None:
        self.relationships.extend(relationships)

    async def get_entities_by_chunk_ids(self, chunk_ids, tenant_context):  # pragma: no cover
        return ()


def test_graph_bridge_maps_dtos_to_ingestion_entities_and_relationships() -> None:
    graph = _FakeGraphRepository()
    bridge = MeetingGraphIndexBridge(graph_repository=graph)
    entities = (
        MeetingGraphEntity(name="Ada", entity_type="Person"),
        MeetingGraphEntity(name="Room 4", entity_type="Place"),
    )
    relationships = (
        MeetingGraphRelationship(
            source_name="Ada",
            source_type="Person",
            target_name="Room 4",
            target_type="Place",
            relationship_type="ATTENDED_AT",
        ),
    )
    asyncio.run(
        bridge.index_meeting(
            tenant_context=_ctx(), entities=entities, relationships=relationships
        )
    )
    assert {e.name for e in graph.entities} == {"Ada", "Room 4"}
    assert all(e.tenant_id == _TENANT for e in graph.entities)
    assert len(graph.relationships) == 1
    rel = graph.relationships[0]
    assert rel.source.name == "Ada" and rel.target.name == "Room 4"
    assert rel.relationship_type == "ATTENDED_AT"
    assert isinstance(rel.source_chunk_id, UUID)  # deterministic synthetic id


# ----------------------------------------------------- refresh adapter


def _event(event_id: str = "evt-1") -> CalendarEvent:
    return CalendarEvent(
        google_event_id=event_id,
        status=CalendarEventStatus.CONFIRMED,
        summary="Board sync",
        start="2026-06-02T15:00:00+00:00",
        organizer_email="chair@x.com",
    )


class _FakeEventSource:
    def __init__(self, *, raise_error: bool = False) -> None:
        self._raise = raise_error
        self.full_calls = 0

    async def list_events_full(self, **_kwargs) -> CalendarEventPage:
        self.full_calls += 1
        if self._raise:
            raise CalendarSourceError("nango proxy 503")
        return CalendarEventPage(events=(_event(),), next_sync_token=None)

    async def list_events_incremental(self, **_kwargs) -> CalendarEventPage:  # pragma: no cover
        return CalendarEventPage(events=())


class _FakeConnectionRepo:
    async def save_connection(self, **_kwargs) -> None:  # pragma: no cover
        return None

    async def get_connection(self, *, tenant_context, connection_id) -> Connection:
        return Connection(
            id=_CONN,
            tenant_id=UUID(_TENANT),
            jurisdiction="eu-west",
            provider="google_calendar",
            provider_config_key="google-calendar",
            provider_connection_ref="ref",
            created_at=_NOW,
            updated_at=_NOW,
        )

    async def get_sync_token(self, *, tenant_context, connection_id):
        return None

    async def set_sync_token(self, *, tenant_context, connection_id, sync_token) -> None:  # pragma: no cover
        return None


class _FakeMeetingStore:
    def __init__(self) -> None:
        self.by_event: dict[str, Any] = {}
        self.embeddings: dict[str, list[float]] = {}

    async def upsert_meeting(self, *, tenant_context, meeting) -> None:
        self.by_event[meeting.google_event_id] = meeting

    async def tombstone_meeting(self, *, tenant_context, google_event_id, cancelled_at) -> None:  # pragma: no cover
        self.by_event.pop(google_event_id, None)

    async def set_embedding(self, *, tenant_context, google_event_id, vector) -> None:
        self.embeddings[google_event_id] = list(vector)

    async def get_by_event_id(self, *, tenant_context, google_event_id):
        return self.by_event.get(google_event_id)

    async def list_meetings(self, *, tenant_context, include_cancelled=False):  # pragma: no cover
        return tuple(self.by_event.values())


def _adapter(source: _FakeEventSource, store: _FakeMeetingStore, graph: _FakeGraphRepository):
    return CalendarRefreshAdapter(
        connection_id=_CONN,
        event_source=source,
        connections=_FakeConnectionRepo(),
        meetings=store,
        meeting_reader=store,
        embedder=MeetingEmbedderBridge(chunk_embedder=_FakeChunkEmbedder()),
        graph_index=MeetingGraphIndexBridge(graph_repository=graph),
    )


def test_refresh_drives_pull_store_index() -> None:
    source = _FakeEventSource()
    store = _FakeMeetingStore()
    graph = _FakeGraphRepository()
    asyncio.run(_adapter(source, store, graph).refresh(tenant_context=_ctx()))
    assert source.full_calls == 1
    assert "evt-1" in store.by_event  # stored
    assert "evt-1" in store.embeddings  # embedded + vector written
    assert graph.entities  # graph-indexed (organizer Person at least)


def test_refresh_maps_source_failure_to_refresh_error() -> None:
    source = _FakeEventSource(raise_error=True)
    store = _FakeMeetingStore()
    graph = _FakeGraphRepository()
    with pytest.raises(CalendarRefreshError):
        asyncio.run(_adapter(source, store, graph).refresh(tenant_context=_ctx()))
