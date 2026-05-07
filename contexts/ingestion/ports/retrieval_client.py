"""RetrievalClient — the read-side port for ingested content (D5 / D65).

Two methods, one for each retrieval mode the platform commits to at
Phase 1:

  - ``search_vector``: cosine-distance search against the chunks
    table's pgvector embedding column. Returns ChunkResults ranked
    by similarity, scoped to the tenant and to sources whose
    pipeline state is ``indexed`` (cross-track readiness per D65).
  - ``traverse_graph``: graph traversal via Neo4j from a seed
    entity to entities reachable within the requested hop depth.
    Returns EntityResults with the relationship-type sequence from
    the seed to each entity, scoped to the tenant and to entities
    whose source chunks belong to indexed sources.

Hybrid composition (vector-and-graph fusion) is explicitly not a
port method per D5 and D65. Hybrid is an agent-layer concern
configured per agent; the port surface keeps each retrieval mode
independent so the agent runtime at P8 and the data-retrieval
design session queued for after P6 close can compose them with
whatever fusion strategy fits the use case.

Both methods take a ``TenantContext`` so the adapters can attribute
their work at the trace level per D41 / D49 / D50. The vector
adapter calls the embedder with ``EmbeddingTask.QUERY`` to embed
the query before search; embedding cost flows through the existing
trace-attribution path with no new architectural surface.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from contexts.ingestion.domain.chunk_result import ChunkResult
from contexts.ingestion.domain.entity_result import EntityResult
from shared_kernel import TenantContext


class RetrievalClient(Protocol):
    async def search_vector(
        self,
        query: str,
        scope: TenantContext,
        limit: int,
    ) -> Sequence[ChunkResult]:
        """Return up to ``limit`` chunks ranked by cosine similarity.

        Scope-restricted to the tenant in ``scope`` and to chunks
        whose source is in the ``indexed`` state. Returns an empty
        sequence when no chunks match (e.g. the tenant has no
        indexed sources, or the query embedding does not surface
        anything within the index). Implementations embed the query
        with ``EmbeddingTask.QUERY`` to apply the model's
        query-side prefix.
        """
        ...

    async def traverse_graph(
        self,
        seed: str,
        scope: TenantContext,
        depth: int,
    ) -> Sequence[EntityResult]:
        """Return entities reachable from the seed within ``depth`` hops.

        ``seed`` matches against ``Entity.name`` for the tenant in
        ``scope``. Depth is the maximum hop count of the traversal;
        depth=0 returns only the seed entity. Returns an empty
        sequence when the seed entity is not present for the tenant
        or when no reachable entities surface from indexed sources.
        Each EntityResult carries the relationship-type sequence
        along the shortest path from the seed.
        """
        ...
