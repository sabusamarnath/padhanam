"""Consumer ports for indexing a Meeting into the inherited substrate (D148).

Per the substrate-inheritance survey, calendar inherits the embedding
capability and the graph store rather than re-implementing either. It
reaches them through these consumer-defined ports (its own thin shapes,
against its own DTOs), which the apps/ composition root bridges to
ingestion's ChunkEmbedderPort and GraphRepositoryPort adapters — the
daily-briefing consumer-port-plus-wiring-adapter precedent (D146). The
calendar context never imports ingestion internals (D16/D17/D28).
"""

from __future__ import annotations

from typing import Protocol, Sequence

from contexts.calendar.domain.meeting_graph import (
    MeetingGraphEntity,
    MeetingGraphRelationship,
)
from shared_kernel.tenant_context import TenantContext


class MeetingEmbeddingPort(Protocol):
    async def embed(
        self, *, text: str, tenant_context: TenantContext
    ) -> Sequence[float]:
        """Embed synthesised Meeting text to a vector (document task)."""
        ...


class MeetingGraphIndexPort(Protocol):
    async def index_meeting(
        self,
        *,
        tenant_context: TenantContext,
        entities: Sequence[MeetingGraphEntity],
        relationships: Sequence[MeetingGraphRelationship],
    ) -> None:
        """Merge a Meeting's entities and relationships into the graph."""
        ...
