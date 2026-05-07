"""pgvector cosine-distance retrieval adapter (D65).

Implements ``RetrievalClient.search_vector`` against the per-tenant
chunks table. Embeds the query via the LiteLLM embedder with
``EmbeddingTask.QUERY`` (so the nomic-embed-text v1.5
``search_query:`` prefix applies symmetrically to the corpus-side
``search_document:`` prefix the worker emitted at S20), then
performs cosine-distance search using pgvector's ``<=>`` operator
against the HNSW index ``chunks_embedding_hnsw_idx`` from S20.

Cross-track readiness per D65: the SQL query joins ``chunks`` to
``sources`` and filters ``sources.state = 'indexed'``. Half-ingested
sources (parsing/embedding/extracting; or any failure state) do not
surface in retrieval until both tracks complete. The join is cheap
because ``sources`` is small at Phase 1 corpus sizes; HNSW
iterative scan in pgvector 0.8.x supports filter pushdown so the
WHERE clause does not defeat the index.

Tenant scoping per D24 / D32: the WHERE clause pins both
``chunks.tenant_id`` and ``sources.tenant_id`` to the bound
tenant. The per-tenant Postgres instance topology per D32 already
makes cross-tenant retrieval structurally impossible at the
database level; the WHERE clause is defence-in-depth, not the
primary isolation mechanism.

Similarity score: the query exposes ``1 - (embedding <=> query)``
which converts cosine distance to cosine similarity in the
``[0, 1]`` range that downstream consumers (the agent runtime,
the evaluation harness) read as a similarity rather than a
distance. The conversion is at the SQL boundary; the domain stays
distance-agnostic.
"""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.ingestion.domain.chunk_result import ChunkResult
from contexts.ingestion.domain.embedding_task import EmbeddingTask
from contexts.ingestion.domain.state import SourceState
from contexts.ingestion.ports.chunk_embedder_port import ChunkEmbedderPort
from shared_kernel import TenantContext


_SEARCH_SQL = sa.text(
    """
    SELECT
        c.id AS id,
        c.source_id AS source_id,
        c.tenant_id AS tenant_id,
        c.jurisdiction AS jurisdiction,
        c.content AS content,
        c.structural_metadata AS structural_metadata,
        c.created_at AS created_at,
        1.0 - (c.embedding <=> CAST(:query_vec AS vector)) AS similarity_score
    FROM chunks c
    JOIN sources s ON s.id = c.source_id
    WHERE s.tenant_id = :tenant_id
      AND c.tenant_id = :tenant_id
      AND s.state = :indexed_state
      AND c.embedding IS NOT NULL
    ORDER BY c.embedding <=> CAST(:query_vec AS vector)
    LIMIT :limit
    """
)


class PgVectorSearch:
    """Implements ``RetrievalClient.search_vector`` (D65).

    The adapter is constructed per-tenant: the session_factory is
    bound to the tenant's data plane via ``async_sessionmaker``,
    same pattern S19's ``PostgresSourceRepository`` uses. The
    embedder is shared across tenants because LiteLLM-side
    routing already takes the tenant context for cost attribution.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedder: ChunkEmbedderPort,
    ) -> None:
        self._session_factory = session_factory
        self._embedder = embedder

    async def search_vector(
        self,
        query: str,
        scope: TenantContext,
        limit: int,
    ) -> Sequence[ChunkResult]:
        if limit <= 0:
            return []

        query_vector = await self._embedder.embed_query(
            query, scope, EmbeddingTask.QUERY
        )
        params = {
            "query_vec": _format_vector_literal(query_vector),
            "tenant_id": scope.tenant_id,
            "indexed_state": SourceState.INDEXED.value,
            "limit": limit,
        }
        async with self._session_factory() as session:
            result = await session.execute(_SEARCH_SQL, params)
            rows = result.mappings().all()
        return [
            ChunkResult(
                chunk_id=UUID(str(row["id"])),
                source_id=UUID(str(row["source_id"])),
                tenant_id=row["tenant_id"],
                jurisdiction=row["jurisdiction"],
                content=row["content"],
                structural_metadata=row["structural_metadata"] or {},
                similarity_score=float(row["similarity_score"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]


def _format_vector_literal(vector: Sequence[float]) -> str:
    """Format a sequence of floats as a pgvector text literal.

    Same shape as the writer-side helper in
    ``PostgresSourceRepository.upsert_chunk_embeddings``. Avoids the
    pgvector Python binding's asyncpg codec-registration surface
    per the S20 reasoning; the dimension is enforced at the column
    type so a wrong-dimension query produces a Postgres error
    rather than a silent mismatch.
    """
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"
