"""Citation candidate domain value objects (D96, S32).

Two frozen-dataclass value objects plus a discriminated union surface
the citation candidates the agent runtime produces from tool
invocation results. The runtime accumulator at ``invoke_agent``
absorbs these from ``ToolCallCompleted`` events across a run,
deduplicates within the run, and passes them to the
``RunHistoryWriter`` consumer port for persistence per D96's single-
transaction multi-table write commitment.

``ChunkCitationCandidate`` carries chunk-shaped attribution surfaced
by retrieval against per-tenant Postgres chunks; the
``source_snapshot`` JSONB-shaped mapping preserves source-level
attribution (Phase 1 carries ``file_name`` and ``file_type`` joined
from the ``sources`` table at retrieval time; richer ingestion
enrichment fills more fields without schema change per D96).
``content_snapshot`` carries the chunk content verbatim at retrieval
time so the citation surface survives source removal per D94's
audit-evidence-fidelity claim.

``EntityCitationCandidate`` carries entity-shaped attribution surfaced
by Neo4j graph traversal. The ``(entity_tenant_id, entity_name,
entity_type)`` composite is the documented join key back to the
Neo4j entity per D64; ``source_chunk_ids`` snapshots the entity's
provenance trail back to per-tenant Postgres chunks so the audit-
evidence-fidelity claim from D94 holds for entity provenance the
same way it holds for chunk content.

Discriminated union ``CitationCandidate`` is the field type the
``ToolCallCompleted`` event carries; consumers branch on type for
storage (the run-history adapter routes to chunk vs entity table)
and for rendering (Phase 2 UX dispatches by type to render the
appropriate citation shape).

Per-type invariants stay tight in ``__post_init__`` rather than
collapsing onto a single polymorphic type with a ``citation_kind``
discriminator per D96 alternative (c). The structural duplication is
the intentional cost of per-type clarity at the domain layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import UUID


@dataclass(frozen=True)
class ChunkCitationCandidate:
    """Citation candidate produced by chunk-level retrieval (D96).

    Carries the chunk identity plus content snapshot plus structured
    source-level snapshot. The runtime accumulator at
    ``invoke_agent`` deduplicates by ``(chunk_id, run_id)`` first-
    seen-wins; the run-history adapter persists into the per-tenant
    ``run_chunk_citations`` table.

    Invariants enforced in ``__post_init__``:

    - ``tenant_id`` non-empty (mirrors the schema CHECK).
    - ``jurisdiction`` non-empty (mirrors the D50 TenantContext discipline).
    - ``chunk_index >= 0`` (mirrors the chunks.chunk_index column).
    - ``content_snapshot`` non-empty (a chunk with no content is not
      a valid citation candidate; retrieval cannot return zero-length
      content for an indexed chunk per the ingestion path).

    The ``source_snapshot`` mapping is opaque at the domain layer
    per D96's structural-JSONB framing; specific keys (Phase 1:
    ``file_name``, ``file_type``) are documented at the adapter
    that populates them. Empty mapping is accepted (forward-
    affordance for tools that surface chunks without source-level
    metadata; today's retrieval always populates the Phase 1 keys).
    """

    chunk_id: UUID
    source_id: UUID
    chunk_index: int
    content_snapshot: str
    source_snapshot: Mapping[str, Any]
    tenant_id: str
    jurisdiction: str

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError(
                "ChunkCitationCandidate.tenant_id must be non-empty"
            )
        if not self.jurisdiction:
            raise ValueError(
                "ChunkCitationCandidate.jurisdiction must be non-empty"
            )
        if self.chunk_index < 0:
            raise ValueError(
                f"ChunkCitationCandidate.chunk_index must be >= 0; "
                f"got {self.chunk_index}"
            )
        if not self.content_snapshot:
            raise ValueError(
                "ChunkCitationCandidate.content_snapshot must be non-empty"
            )


@dataclass(frozen=True)
class EntityCitationCandidate:
    """Citation candidate produced by graph-level retrieval (D96).

    Carries the Neo4j entity composite key plus the source_chunk_ids
    provenance snapshot. The runtime accumulator at ``invoke_agent``
    deduplicates by ``(entity_tenant_id, entity_name, entity_type,
    run_id)`` first-seen-wins; the run-history adapter persists into
    the per-tenant ``run_entity_citations`` table.

    Invariants enforced in ``__post_init__``:

    - ``entity_tenant_id`` non-empty (mirrors the schema CHECK).
    - ``entity_name`` non-empty.
    - ``entity_type`` non-empty.
    - ``tenant_id`` non-empty.
    - ``jurisdiction`` non-empty.
    - ``entity_tenant_id == tenant_id``: the entity's tenant property
      from Neo4j matches the runtime's bound tenant per D63's
      tenant-property-based scoping; mismatch would indicate cross-
      tenant data leak the candidate type structurally rejects.

    ``source_chunk_ids`` is an empty tuple by default (forward-
    affordance for entities with no recorded source chunks; today's
    ingestion always populates the array).
    """

    entity_tenant_id: str
    entity_name: str
    entity_type: str
    source_chunk_ids: tuple[UUID, ...]
    tenant_id: str
    jurisdiction: str

    def __post_init__(self) -> None:
        if not self.entity_tenant_id:
            raise ValueError(
                "EntityCitationCandidate.entity_tenant_id must be non-empty"
            )
        if not self.entity_name:
            raise ValueError(
                "EntityCitationCandidate.entity_name must be non-empty"
            )
        if not self.entity_type:
            raise ValueError(
                "EntityCitationCandidate.entity_type must be non-empty"
            )
        if not self.tenant_id:
            raise ValueError(
                "EntityCitationCandidate.tenant_id must be non-empty"
            )
        if not self.jurisdiction:
            raise ValueError(
                "EntityCitationCandidate.jurisdiction must be non-empty"
            )
        if self.entity_tenant_id != self.tenant_id:
            raise ValueError(
                "EntityCitationCandidate.entity_tenant_id must match "
                f"tenant_id; got entity_tenant_id={self.entity_tenant_id!r} "
                f"tenant_id={self.tenant_id!r}"
            )


CitationCandidate = ChunkCitationCandidate | EntityCitationCandidate
"""Discriminated union over the two citation candidate kinds (D96)."""


__all__ = [
    "ChunkCitationCandidate",
    "EntityCitationCandidate",
    "CitationCandidate",
]
