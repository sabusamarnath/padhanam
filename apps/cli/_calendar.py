"""Calendar composition-root wiring (D146, D148, D149, D150, P15, S55b-1).

The consumer deferred from S55a: this is where calendar's inherited
indexing ports (``MeetingEmbeddingPort``, ``MeetingGraphIndexPort``) bridge
to ingestion's ``ChunkEmbedderPort`` and ``GraphRepositoryPort`` adapters,
and where the D150 refresh-before-answer port wraps the D149
``sync_calendar`` scoped full pull driven by the real Nango Proxy adapter.
Living at the apps composition root (not inside a context) keeps the
calendar and calendar_conversation contexts free of ingestion internals
per D16/D17/D28 — the daily-briefing consumer-port-plus-wiring-adapter
precedent (D146).

Nothing here is imported by a context; S55b-2 dispatches the cell and
consumes ``build_calendar_refresh_adapter``.
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from contexts.calendar.application.sync_calendar import sync_calendar
from contexts.calendar.domain.errors import (
    CalendarSourceConfigurationError,
    CalendarSourceError,
    NoSuchConnectionError,
    SyncTokenExpiredError,
)
from contexts.calendar.domain.meeting_graph import (
    MeetingGraphEntity,
    MeetingGraphRelationship,
)
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
from contexts.calendar_conversation.application.ports.calendar_refresh import (
    CalendarRefreshError,
)
from contexts.ingestion.domain.embedding_task import EmbeddingTask
from contexts.ingestion.domain.entity import Entity
from contexts.ingestion.domain.relationship import EntityRef, Relationship
from contexts.ingestion.ports.chunk_embedder_port import (
    ChunkEmbedderPort,
    EmbedderConfigurationError,
    EmbedderError,
)
from contexts.ingestion.ports.graph_repository_port import (
    GraphRepositoryConfigurationError,
    GraphRepositoryError,
    GraphRepositoryPort,
)
from shared_kernel import TenantContext
from typing import Sequence


class MeetingEmbedderBridge:
    """Implements calendar's ``MeetingEmbeddingPort`` over ingestion's embedder.

    Synthesised Meeting text is a single string, so the bridge calls the
    inherited ``embed_query`` (single-text → single-vector) with the
    DOCUMENT task (the substrate-inheritance survey: a Meeting is indexed
    document-side, D148). No embedding logic is re-implemented.
    """

    def __init__(self, *, chunk_embedder: ChunkEmbedderPort) -> None:
        self._embedder = chunk_embedder

    async def embed(
        self, *, text: str, tenant_context: TenantContext
    ) -> Sequence[float]:
        return await self._embedder.embed_query(
            text, tenant_context, task=EmbeddingTask.DOCUMENT
        )


class MeetingGraphIndexBridge:
    """Implements calendar's ``MeetingGraphIndexPort`` over ingestion's graph.

    Maps calendar's structured ``MeetingGraphEntity`` / ``MeetingGraphRelationship``
    DTOs to ingestion's ``Entity`` / ``Relationship`` domain shapes and
    MERGEs them via the inherited ``GraphRepositoryPort``. A Meeting has no
    chunk, so a deterministic ``source_chunk_id`` is synthesised from the
    tenant + relationship triple (stable across refreshes for idempotent
    MERGE). Entities are merged before relationships per the port contract.
    """

    def __init__(self, *, graph_repository: GraphRepositoryPort) -> None:
        self._graph = graph_repository

    async def index_meeting(
        self,
        *,
        tenant_context: TenantContext,
        entities: Sequence[MeetingGraphEntity],
        relationships: Sequence[MeetingGraphRelationship],
    ) -> None:
        tid = tenant_context.tenant_id
        juris = tenant_context.jurisdiction
        mapped_entities = [
            Entity(
                tenant_id=tid,
                jurisdiction=juris,
                name=e.name,
                entity_type=e.entity_type,
            )
            for e in entities
        ]
        mapped_relationships = [
            Relationship(
                tenant_id=tid,
                jurisdiction=juris,
                source=EntityRef(name=r.source_name, entity_type=r.source_type),
                target=EntityRef(name=r.target_name, entity_type=r.target_type),
                relationship_type=r.relationship_type,
                source_chunk_id=_synthetic_chunk_id(tid, r),
            )
            for r in relationships
        ]
        if mapped_entities:
            await self._graph.merge_entities(mapped_entities, tenant_context)
        if mapped_relationships:
            await self._graph.merge_relationships(
                mapped_relationships, tenant_context
            )


def _synthetic_chunk_id(tenant_id: str, r: MeetingGraphRelationship) -> UUID:
    key = (
        f"{tenant_id}:{r.source_type}:{r.source_name}:"
        f"{r.relationship_type}:{r.target_type}:{r.target_name}"
    )
    return uuid5(NAMESPACE_URL, key)


class CalendarRefreshAdapter:
    """Implements ``CalendarRefreshPort`` over the D149 ``sync_calendar`` pull.

    Bound to one tenant's calendar connection. ``refresh`` runs the scoped
    full pull (store + index) and returns on success; any calendar-source
    or pipeline failure (Nango/Google unreachable, auth, missing
    connection) is mapped to ``CalendarRefreshError`` so the cell serves
    the cached store with a staleness note rather than failing the turn
    (D150 Option A).
    """

    def __init__(
        self,
        *,
        connection_id: UUID,
        event_source: CalendarEventSourcePort,
        connections: ConnectionRepository,
        meetings: MeetingRepository,
        meeting_reader: MeetingReader,
        embedder: MeetingEmbeddingPort,
        graph_index: MeetingGraphIndexPort,
        trigger: CalendarSyncTrigger = CalendarSyncTrigger.POLL,
    ) -> None:
        self._connection_id = connection_id
        self._event_source = event_source
        self._connections = connections
        self._meetings = meetings
        self._meeting_reader = meeting_reader
        self._embedder = embedder
        self._graph_index = graph_index
        self._trigger = trigger

    async def refresh(self, *, tenant_context: TenantContext) -> None:
        try:
            await sync_calendar(
                tenant_context=tenant_context,
                connection_id=self._connection_id,
                trigger=self._trigger,
                event_source=self._event_source,
                connections=self._connections,
                meetings=self._meetings,
                meeting_reader=self._meeting_reader,
                embedder=self._embedder,
                graph_index=self._graph_index,
            )
        except (
            CalendarSourceError,
            CalendarSourceConfigurationError,
            SyncTokenExpiredError,
            NoSuchConnectionError,
            EmbedderError,
            EmbedderConfigurationError,
            GraphRepositoryError,
            GraphRepositoryConfigurationError,
        ) as exc:
            raise CalendarRefreshError(
                f"calendar refresh failed: {type(exc).__name__}: {exc}"
            ) from exc


__all__ = [
    "CalendarRefreshAdapter",
    "MeetingEmbedderBridge",
    "MeetingGraphIndexBridge",
    "build_calendar_refresh_adapter",
]


def build_calendar_refresh_adapter(
    *,
    tenant_id: str,
    connection_id: UUID,
) -> CalendarRefreshAdapter:  # pragma: no cover - composition-root wiring
    """Construct the refresh adapter wired to the real source/embedder/graph.

    The composition seam S55b-2 calls to drive a refresh from a user turn.
    Imports the concrete adapters lazily so this module stays importable
    without a live stack (the integration test exercises the adapter
    classes above with doubles; this builder is exercised at the live
    smoke).
    """
    from apps.cli._runtime import build_tenant_wiring
    from contexts.calendar.adapters.outbound.nango.nango_proxy_calendar_adapter import (
        NangoProxyCalendarAdapter,
    )
    from contexts.calendar.adapters.outbound.postgres.connection_repository import (
        PostgresConnectionRepository,
    )
    from contexts.calendar.adapters.outbound.postgres.meeting_store import (
        PostgresMeetingStore,
    )
    from contexts.ingestion.adapters.outbound.embedding import LiteLLMChunkEmbedder
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import CalendarSettings, Neo4jSettings
    from shared_kernel import TenantId

    wiring = build_tenant_wiring(tenant_id)
    session_factory = wiring.session_factory

    async def _resolver(_tid: TenantId):
        return session_factory

    bound = TenantId(str(wiring.tenant_context.tenant_id))
    connections = PostgresConnectionRepository(
        per_tenant_sessionmaker_resolver=_resolver, bound_tenant_id=bound
    )
    store = PostgresMeetingStore(
        per_tenant_sessionmaker_resolver=_resolver, bound_tenant_id=bound
    )
    settings = CalendarSettings()
    event_source = NangoProxyCalendarAdapter(
        base_url=settings.nango_base_url, secret_key=settings.nango_secret_key
    )
    embedder = MeetingEmbedderBridge(chunk_embedder=LiteLLMChunkEmbedder())
    graph_index = MeetingGraphIndexBridge(
        graph_repository=Neo4jGraphRepository.from_settings(Neo4jSettings())
    )
    return CalendarRefreshAdapter(
        connection_id=connection_id,
        event_source=event_source,
        connections=connections,
        meetings=store,
        meeting_reader=store,
        embedder=embedder,
        graph_index=graph_index,
    )
