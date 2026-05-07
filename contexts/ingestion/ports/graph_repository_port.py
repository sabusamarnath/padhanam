"""GraphRepositoryPort — the graph-store-as-port shape (D63 / D64).

The graph repository writes Entities and Relationships extracted
from a Source's chunks into the shared Neo4j instance, and reads
them back for verification or downstream consumption. Tenant
isolation is enforced inside the adapter through the
``TenantScopedNeo4jSession`` wrapper per D63: every Cypher query
the adapter issues runs with the bound tenant_id predicate auto-
applied, so a port-level call cannot accidentally cross tenant
boundaries.

Each call carries a ``TenantContext`` so the adapter can construct
a tenant-scoped session for the duration of the call. The
``Sequence`` return types preserve the brief's port-shape commitment
without leaking adapter pagination concerns into the contract;
the adapter materialises results internally and returns the full
list, which is appropriate at Phase 1 corpus sizes (dozens of
sources, hundreds of entities per source).

Errors: adapters raise ``GraphRepositoryError`` for retryable infra
failures (Neo4j unreachable, transaction timeout, deadlock) and
``GraphRepositoryConfigurationError`` for non-retryable ones
(authentication, schema mismatch, malformed Cypher template).
The ``extract_source`` worker use case translates both into the
``extraction_failed`` source state with ``extraction_error_text``
populated; the operator's retry surface is manual transition back
to ``embedded``.
"""

from __future__ import annotations

from typing import Protocol, Sequence
from uuid import UUID

from contexts.ingestion.domain.entity import Entity
from contexts.ingestion.domain.relationship import Relationship
from shared_kernel import TenantContext


class GraphRepositoryError(Exception):
    """Retryable infrastructure failure during a graph operation
    (Neo4j unreachable, transaction timeout, deadlock). The worker
    writes ``extraction_failed`` and the operator can retry by
    manually transitioning back to ``embedded``."""


class GraphRepositoryConfigurationError(Exception):
    """Non-retryable configuration failure (auth, schema mismatch,
    malformed Cypher template). Same handling as
    ``GraphRepositoryError`` at S21 — separated here so future
    retry policy can branch on the distinction."""


class GraphRepositoryPort(Protocol):
    async def merge_entities(
        self,
        entities: Sequence[Entity],
        tenant_context: TenantContext,
    ) -> None:
        """Idempotently MERGE entities by ``(tenant_id, name,
        entity_type)``. Re-running with the same composite updates
        ``source_chunk_ids`` additively (chunk ids accumulate so
        re-extraction over different chunks adds provenance) and
        leaves ``created_at`` from the first MERGE intact.
        """
        ...

    async def merge_relationships(
        self,
        relationships: Sequence[Relationship],
        tenant_context: TenantContext,
    ) -> None:
        """Idempotently MERGE relationships by their composite
        uniqueness key per D64. Endpoint Entities must already
        exist (caller orchestrates entity merge first); the
        adapter MERGEs the relationship between the existing
        endpoints and does not create endpoint nodes implicitly.
        """
        ...

    async def get_entities_by_chunk_ids(
        self,
        chunk_ids: Sequence[UUID],
        tenant_context: TenantContext,
    ) -> Sequence[Entity]:
        """Return all entities whose ``source_chunk_ids`` overlap
        the given chunk ids and that match the bound tenant.
        Empty input returns an empty sequence; the adapter does not
        raise on empty input.
        """
        ...

    async def get_relationships_by_chunk_ids(
        self,
        chunk_ids: Sequence[UUID],
        tenant_context: TenantContext,
    ) -> Sequence[Relationship]:
        """Return all relationships whose ``source_chunk_id``
        appears in the given chunk ids and that match the bound
        tenant. Empty input returns an empty sequence; the adapter
        does not raise on empty input.
        """
        ...
