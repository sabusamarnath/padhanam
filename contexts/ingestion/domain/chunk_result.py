"""ChunkResult value object — vector retrieval row (D65).

The RetrievalClient.search_vector method returns ChunkResults: one
per matching chunk, ranked by cosine similarity. The shape mirrors
the Chunk domain object for content/metadata fields and adds the
similarity_score the search produced. Tenant-scoped per D24 / D32:
the adapter's WHERE clause pins ``tenant_id`` so cross-tenant
results structurally cannot land in the response.

Frozen dataclass per D16. Validation in ``__post_init__`` rejects
empty tenant_id and missing jurisdiction per D50's TenantContext
discipline applied to the result shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping
from uuid import UUID


@dataclass(frozen=True)
class ChunkResult:
    chunk_id: UUID
    source_id: UUID
    tenant_id: str
    jurisdiction: str
    content: str
    structural_metadata: Mapping[str, object]
    similarity_score: float
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError("ChunkResult.tenant_id must be non-empty")
        if not self.jurisdiction:
            raise ValueError("ChunkResult.jurisdiction must be non-empty")
