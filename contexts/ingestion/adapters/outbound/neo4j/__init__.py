"""Neo4j outbound adapter for the ingestion context (D63 / D64).

The only place ``import neo4j`` enters the codebase outside the
``ops.migrate_neo4j`` Cypher migration runner. The
``neo4j-confined`` import-linter contract plus the AST enforcement
test at ``tests/_enforcement/test_no_raw_neo4j_session.py`` fence
the boundary mechanically.

Public surface:

- ``Neo4jGraphRepository`` — the ``GraphRepositoryPort``
  implementation. The application layer constructs one per
  process and passes it into the ``extract_source`` use case.

- ``TenantScopedNeo4jSession`` — the wrapper that owns the bolt
  driver session for the duration of a single tenant-scoped
  operation. Every Cypher template inside the wrapper auto-binds
  the bound tenant_id predicate, so missing-predicate Cypher
  cannot exist in callable code per D63's enforcement commitment.
"""

from contexts.ingestion.adapters.outbound.neo4j.graph_repository import (
    Neo4jGraphRepository,
    make_async_driver,
)
from contexts.ingestion.adapters.outbound.neo4j.session import (
    TenantScopedNeo4jSession,
)

__all__ = [
    "Neo4jGraphRepository",
    "TenantScopedNeo4jSession",
    "make_async_driver",
]
