"""EntityResult value object — graph traversal row (D65).

The RetrievalClient.traverse_graph method returns EntityResults:
one per reachable entity from the seed within the requested depth,
each carrying the relationship-type sequence from the seed to that
entity (the ``relationship_path`` tuple). The seed itself appears
with an empty path. Tenant-scoped per D24 / D63: the underlying
TenantScopedNeo4jSession wrapper auto-binds the tenant predicate so
cross-tenant results structurally cannot land in the response.

Frozen dataclass per D16. Validation in ``__post_init__`` rejects
empty tenant_id and missing jurisdiction per D50's TenantContext
discipline applied to the result shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
from uuid import UUID


@dataclass(frozen=True)
class EntityResult:
    tenant_id: str
    jurisdiction: str
    name: str
    entity_type: str
    source_chunk_ids: Sequence[UUID]
    relationship_path: Sequence[str]
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError("EntityResult.tenant_id must be non-empty")
        if not self.jurisdiction:
            raise ValueError("EntityResult.jurisdiction must be non-empty")
