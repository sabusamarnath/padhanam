"""Neo4j graph-traversal retrieval adapter (D65).

Implements ``RetrievalClient.traverse_graph`` against the shared
Neo4j instance via the ``TenantScopedNeo4jSession`` wrapper from
S21. Variable-length path traversal from a seed entity returns
entities reachable within the requested hop count, with the
relationship-type sequence along the shortest path captured.

Cross-track readiness per D65: the readiness filter is enforced
through a chunk-id set computed against per-tenant Postgres and
passed as a Cypher parameter for the
``ANY(cid IN reachable.source_chunk_ids WHERE cid IN
$indexed_chunk_ids)`` predicate. Entities whose source chunks come
only from non-indexed sources do not surface. The adapter takes a
session_factory for per-tenant Postgres alongside the Neo4j driver
and the bound TenantContext.

Tenant scoping per D24 / D63: the wrapper auto-binds the
``$tenant_id`` predicate at every Cypher execution. Cross-tenant
traversal is structurally impossible at the wrapper boundary.
"""

from __future__ import annotations

from typing import Any, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.ingestion.adapters.outbound.neo4j.session import (
    TenantScopedNeo4jSession,
)
from contexts.ingestion.domain.entity_result import EntityResult
from contexts.ingestion.domain.state import SourceState
from shared_kernel import TenantContext


_INDEXED_CHUNK_IDS_SQL = sa.text(
    """
    SELECT c.id
    FROM chunks c
    JOIN sources s ON s.id = c.source_id
    WHERE s.tenant_id = :tenant_id
      AND c.tenant_id = :tenant_id
      AND s.state = :indexed_state
    """
)


class Neo4jTraverse:
    """Implements ``RetrievalClient.traverse_graph`` (D65).

    Constructed with the shared Neo4j driver and the per-tenant
    Postgres session factory. ``traverse_graph`` opens a tenant-
    scoped Neo4j session per call (mirroring the
    ``Neo4jGraphRepository`` pattern from S21) and reads the set of
    indexed chunk_ids from per-tenant Postgres before issuing the
    traversal.
    """

    def __init__(
        self,
        driver: Any,
        pg_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        # ``driver`` is a ``neo4j.AsyncDriver``; the type is left as
        # ``Any`` so this module avoids importing the neo4j package
        # directly per D63's "wrapper is the single neo4j surface"
        # commitment. The wrapper at ``TenantScopedNeo4jSession`` is
        # the only place that touches driver internals.
        self._driver = driver
        self._pg_session_factory = pg_session_factory

    async def traverse_graph(
        self,
        seed: str,
        scope: TenantContext,
        depth: int,
    ) -> Sequence[EntityResult]:
        if depth < 0:
            raise ValueError(f"depth must be non-negative, got {depth}")

        indexed_chunk_ids = await self._read_indexed_chunk_ids(scope)
        if not indexed_chunk_ids:
            # No indexed sources ⇒ the readiness predicate excludes
            # everything; short-circuit before the Cypher query.
            return []

        async with TenantScopedNeo4jSession(self._driver, scope) as session:
            rows = await session.traverse_from_seed(
                seed_name=seed,
                depth=depth,
                indexed_chunk_ids=indexed_chunk_ids,
            )
        return [
            EntityResult(
                tenant_id=row["tenant_id"],
                jurisdiction=row["jurisdiction"],
                name=row["name"],
                entity_type=row["entity_type"],
                source_chunk_ids=tuple(
                    UUID(cid) for cid in row["source_chunk_ids"]
                ),
                relationship_path=tuple(row["relationship_path"] or ()),
                created_at=_to_python_datetime(row["created_at"]),
            )
            for row in rows
        ]

    async def _read_indexed_chunk_ids(
        self, scope: TenantContext
    ) -> list[UUID]:
        params = {
            "tenant_id": scope.tenant_id,
            "indexed_state": SourceState.INDEXED.value,
        }
        async with self._pg_session_factory() as session:
            result = await session.execute(_INDEXED_CHUNK_IDS_SQL, params)
            rows = result.scalars().all()
        return [UUID(str(row)) for row in rows]


def _to_python_datetime(value: object):
    """Mirror of the helper in session.py — unwrap the Neo4j
    AsyncSession's DateTime subclass into a stdlib datetime.
    """
    from datetime import datetime

    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    to_native = getattr(value, "to_native", None)
    if to_native is not None:
        return to_native()
    raise TypeError(f"unexpected datetime shape from neo4j driver: {value!r}")
