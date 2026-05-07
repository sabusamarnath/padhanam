"""Retrieval adapters for the ingestion context (D65).

Two adapters land at S22 implementing ``RetrievalClient.search_vector``
and ``RetrievalClient.traverse_graph``:

  - ``PgVectorSearch`` against the chunks table on per-tenant
    Postgres via cosine distance against the HNSW index from S20.
  - ``Neo4jTraverse`` against the shared Neo4j instance via the
    ``TenantScopedNeo4jSession`` wrapper from S21.

Both apply the cross-track readiness filter D65 commits to:
chunks (and entities derived from chunks) only surface when their
source's pipeline state is ``indexed`` — half-ingested sources do
not surface in retrieval until both tracks complete.
"""

from contexts.ingestion.adapters.outbound.retrieval.pgvector_search import (
    PgVectorSearch,
)

__all__ = ["PgVectorSearch"]
