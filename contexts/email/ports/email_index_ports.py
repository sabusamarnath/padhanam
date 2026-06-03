"""Consumer ports for indexing an Email into the inherited substrate (D151).

Per the substrate-inheritance discipline (the calendar precedent), email
inherits the embedding capability and the graph store through its own thin
consumer ports — its own shapes against its own DTOs — which the apps/
composition root bridges to ingestion's ``ChunkEmbedderPort`` and
``GraphRepositoryPort`` adapters. The email context never imports ingestion
internals (D16/D17/D28). The embedding port is plural (``embed_chunks``)
because email bodies are chunked, unlike calendar's single meeting vector.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from contexts.email.domain.email_graph import (
    EmailGraphEntity,
    EmailGraphRelationship,
)
from shared_kernel.tenant_context import TenantContext


class EmailChunkEmbeddingPort(Protocol):
    async def embed_chunks(
        self, *, contents: Sequence[str], tenant_context: TenantContext
    ) -> Sequence[Sequence[float]]:
        """Embed N chunk texts to N vectors, in input order (document task)."""
        ...


class EmailGraphIndexPort(Protocol):
    async def index_email(
        self,
        *,
        tenant_context: TenantContext,
        entities: Sequence[EmailGraphEntity],
        relationships: Sequence[EmailGraphRelationship],
    ) -> None:
        """Merge an Email's participant entities and correspondence edges."""
        ...
