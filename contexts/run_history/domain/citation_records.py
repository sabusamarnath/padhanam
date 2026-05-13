"""Citation record domain value objects (D96, S32).

Run-history-context-owned record types for the two per-tenant
citation tables. They mirror the agent-context citation candidate
types one-for-one at the type level per the D54 mirror-types-at-
context-boundaries pattern; the wiring adapter at
``apps/cli/_cross_context.py`` translates ``ChunkCitationCandidate``
to ``ChunkCitationRecord`` and ``EntityCitationCandidate`` to
``EntityCitationRecord`` at the producer-side boundary.

The structural duplication is the intentional cost of D17's
boundary discipline: the agent context defines what it produces
(candidates), the run-history context defines what it persists
(records), and the wiring adapter does the field-for-field
translation. Future read-side surfaces at S33 may project these
records further into UX-shaped DTOs without coupling agent-side
concerns into the read path.

Invariants enforced in ``__post_init__`` mirror the schema-layer
CHECK constraints from D95 / D96's revised columns plus the
agent-context candidate invariants the wiring adapter has already
fenced; the producer-side enforcement is defence-in-depth, not the
primary validation boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID


@dataclass(frozen=True)
class ChunkCitationRecord:
    """Persistence-shaped chunk citation row (D96).

    Mirrors the run-history-context ``run_chunk_citations`` table
    column set one-for-one. The adapter constructs instances from
    agent-context ``ChunkCitationCandidate`` DTOs at write time and
    inserts via the ``async with session.begin()`` block per D96's
    single-transaction multi-table write commitment.
    """

    id: UUID
    run_id: UUID
    chunk_id: UUID | None
    tenant_id: str
    jurisdiction: str
    chunk_excerpt: str
    source_snapshot: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError("ChunkCitationRecord.tenant_id must be non-empty")
        if not self.jurisdiction:
            raise ValueError(
                "ChunkCitationRecord.jurisdiction must be non-empty"
            )
        if not self.chunk_excerpt:
            raise ValueError(
                "ChunkCitationRecord.chunk_excerpt must be non-empty"
            )


@dataclass(frozen=True)
class EntityCitationRecord:
    """Persistence-shaped entity citation row (D96).

    Mirrors the run-history-context ``run_entity_citations`` table
    column set one-for-one. The ``source_chunk_ids`` snapshot
    preserves the entity's provenance trail back to per-tenant
    Postgres chunks at retrieval time per D96.
    """

    id: UUID
    run_id: UUID
    entity_tenant_id: str
    entity_name: str
    entity_type: str
    tenant_id: str
    source_chunk_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        if not self.entity_tenant_id:
            raise ValueError(
                "EntityCitationRecord.entity_tenant_id must be non-empty"
            )
        if not self.entity_name:
            raise ValueError(
                "EntityCitationRecord.entity_name must be non-empty"
            )
        if not self.entity_type:
            raise ValueError(
                "EntityCitationRecord.entity_type must be non-empty"
            )
        if not self.tenant_id:
            raise ValueError(
                "EntityCitationRecord.tenant_id must be non-empty"
            )
        if self.entity_tenant_id != self.tenant_id:
            raise ValueError(
                "EntityCitationRecord.entity_tenant_id must match tenant_id"
            )


__all__ = [
    "ChunkCitationRecord",
    "EntityCitationRecord",
]
