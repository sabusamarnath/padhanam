"""Email composition-root wiring (D146, D151, P15, S56a).

Where email's inherited indexing ports bridge to ingestion's
``ChunkEmbedderPort`` (plural ``embed`` over Chunks) and
``GraphRepositoryPort`` adapters, at the apps composition root so the
email context stays free of ingestion internals (D16/D17/D28). The
``build_email_sync_components`` builder wires the real Nango google-mail
adapter + Postgres stores + the bridges for the S56a smoke and S56b.
"""

from __future__ import annotations

from typing import Sequence
from uuid import NAMESPACE_URL, uuid4, uuid5

from contexts.email.domain.email_graph import EmailGraphEntity, EmailGraphRelationship
from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.embedding_task import EmbeddingTask
from contexts.ingestion.domain.entity import Entity
from contexts.ingestion.domain.relationship import EntityRef, Relationship
from contexts.ingestion.ports.chunk_embedder_port import ChunkEmbedderPort
from contexts.ingestion.ports.graph_repository_port import GraphRepositoryPort
from shared_kernel import TenantContext


class EmailChunkEmbedderBridge:
    """EmailChunkEmbeddingPort over ingestion's batch ChunkEmbedderPort.embed.

    Email bodies are chunked (plural), so the batch ``embed`` is the right
    inherited method (calendar used the single ``embed_query``). Wraps each
    chunk text in a transient ingestion ``Chunk`` (the embedder only reads
    ``content``; the synthetic ids are carriers, never persisted to
    ingestion's store).
    """

    def __init__(self, *, chunk_embedder: ChunkEmbedderPort) -> None:
        self._embedder = chunk_embedder

    async def embed_chunks(
        self, *, contents: Sequence[str], tenant_context: TenantContext
    ) -> Sequence[Sequence[float]]:
        if not contents:
            return []
        source_id = uuid4()
        chunks = [
            Chunk(
                id=uuid4(),
                source_id=source_id,
                tenant_id=tenant_context.tenant_id,
                jurisdiction=tenant_context.jurisdiction,
                chunk_index=i,
                content=content,
            )
            for i, content in enumerate(contents)
        ]
        embeddings = await self._embedder.embed(
            chunks, tenant_context, EmbeddingTask.DOCUMENT
        )
        return [list(e.vector) for e in embeddings]


class EmailGraphIndexBridge:
    """EmailGraphIndexPort over ingestion's GraphRepositoryPort."""

    def __init__(self, *, graph_repository: GraphRepositoryPort) -> None:
        self._graph = graph_repository

    async def index_email(
        self,
        *,
        tenant_context: TenantContext,
        entities: Sequence[EmailGraphEntity],
        relationships: Sequence[EmailGraphRelationship],
    ) -> None:
        tid = tenant_context.tenant_id
        juris = tenant_context.jurisdiction
        mapped_entities = [
            Entity(tenant_id=tid, jurisdiction=juris, name=e.name, entity_type=e.entity_type)
            for e in entities
        ]
        mapped_relationships = [
            Relationship(
                tenant_id=tid,
                jurisdiction=juris,
                source=EntityRef(name=r.source_name, entity_type=r.source_type),
                target=EntityRef(name=r.target_name, entity_type=r.target_type),
                relationship_type=r.relationship_type,
                source_chunk_id=uuid5(
                    NAMESPACE_URL,
                    f"{tid}:{r.source_name}:{r.relationship_type}:{r.target_name}",
                ),
            )
            for r in relationships
        ]
        if mapped_entities:
            await self._graph.merge_entities(mapped_entities, tenant_context)
        if mapped_relationships:
            await self._graph.merge_relationships(mapped_relationships, tenant_context)


def build_email_sync_components(*, tenant_id: str):  # pragma: no cover - composition-root wiring
    """Wire the real google-mail adapter + Postgres stores + indexing bridges.

    Returns a dict of the components ``sync_email`` consumes; the S56a smoke
    and S56b call it. Lazy concrete imports keep this module importable
    without a live stack (the bridges above are unit/integration-tested
    with doubles).
    """
    from apps.cli._runtime import build_tenant_wiring
    from contexts.email.adapters.outbound.nango.nango_proxy_email_adapter import (
        NangoProxyEmailAdapter,
    )
    from contexts.email.adapters.outbound.postgres.connection_repository import (
        PostgresConnectionRepository,
    )
    from contexts.email.adapters.outbound.postgres.email_store import (
        PostgresEmailChunkStore,
        PostgresEmailStore,
    )
    from contexts.ingestion.adapters.outbound.embedding import LiteLLMChunkEmbedder
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import EmailSettings, Neo4jSettings
    from shared_kernel import TenantId

    wiring = build_tenant_wiring(tenant_id)
    sf = wiring.session_factory

    async def _resolver(_tid: TenantId):
        return sf

    bound = TenantId(str(wiring.tenant_context.tenant_id))
    settings = EmailSettings()
    return {
        "tenant_context": wiring.tenant_context,
        "message_source": NangoProxyEmailAdapter(
            base_url=settings.nango_base_url, secret_key=settings.nango_secret_key
        ),
        "connections": PostgresConnectionRepository(
            per_tenant_sessionmaker_resolver=_resolver, bound_tenant_id=bound
        ),
        "emails": PostgresEmailStore(
            per_tenant_sessionmaker_resolver=_resolver, bound_tenant_id=bound
        ),
        "email_reader": PostgresEmailStore(
            per_tenant_sessionmaker_resolver=_resolver, bound_tenant_id=bound
        ),
        "chunks": PostgresEmailChunkStore(
            per_tenant_sessionmaker_resolver=_resolver, bound_tenant_id=bound
        ),
        "embedder": EmailChunkEmbedderBridge(chunk_embedder=LiteLLMChunkEmbedder()),
        "graph_index": EmailGraphIndexBridge(
            graph_repository=Neo4jGraphRepository.from_settings(Neo4jSettings())
        ),
    }


class EmailRefreshAdapter:
    """Implements EmailRefreshPort over the D151 sync_email full pull (D152 Option A).

    Bound to one tenant's email connection. ``refresh`` runs the full-pull
    sync (store + chunk + embed + graph) in-turn and returns on success;
    any source/pipeline failure is mapped to ``EmailRefreshError`` so the
    cell serves the cached store with a staleness note. The deferred
    background-sync optimization swaps *this* adapter for a warm-store one
    behind the same port — the cell does not change.
    """

    def __init__(
        self, *, connection_id, message_source, connections, emails, email_reader,
        embedder, graph_index, chunks, trigger=None,
    ) -> None:
        self._connection_id = connection_id
        self._message_source = message_source
        self._connections = connections
        self._emails = emails
        self._email_reader = email_reader
        self._embedder = embedder
        self._graph_index = graph_index
        self._chunks = chunks
        self._trigger = trigger

    async def refresh(self, *, tenant_context) -> None:
        from contexts.email.application.sync_email import sync_email
        from contexts.email.domain.errors import (
            EmailSourceConfigurationError, EmailSourceError, NoSuchConnectionError,
        )
        from contexts.email.domain.sync_trigger import EmailSyncTrigger
        from contexts.email_conversation.application.ports.email_refresh import EmailRefreshError
        from contexts.ingestion.ports.chunk_embedder_port import (
            EmbedderConfigurationError, EmbedderError,
        )
        from contexts.ingestion.ports.graph_repository_port import (
            GraphRepositoryConfigurationError, GraphRepositoryError,
        )

        try:
            await sync_email(
                tenant_context=tenant_context, connection_id=self._connection_id,
                trigger=self._trigger or EmailSyncTrigger.POLL,
                message_source=self._message_source, connections=self._connections,
                emails=self._emails, email_reader=self._email_reader,
                embedder=self._embedder, graph_index=self._graph_index, chunks=self._chunks,
            )
        except (
            EmailSourceError, EmailSourceConfigurationError, NoSuchConnectionError,
            EmbedderError, EmbedderConfigurationError,
            GraphRepositoryError, GraphRepositoryConfigurationError,
        ) as exc:
            raise EmailRefreshError(f"email refresh failed: {type(exc).__name__}: {exc}") from exc


def build_email_refresh_adapter(*, tenant_id: str, connection_id):  # pragma: no cover - composition-root wiring
    """Wire the D152 Option-A refresh adapter (sync_email full-pull-in-turn behind the port)."""
    c = build_email_sync_components(tenant_id=tenant_id)
    return EmailRefreshAdapter(
        connection_id=connection_id, message_source=c["message_source"], connections=c["connections"],
        emails=c["emails"], email_reader=c["email_reader"], embedder=c["embedder"],
        graph_index=c["graph_index"], chunks=c["chunks"],
    )


__all__ = [
    "EmailChunkEmbedderBridge",
    "EmailGraphIndexBridge",
    "EmailRefreshAdapter",
    "build_email_refresh_adapter",
    "build_email_sync_components",
]
