"""Gold-set aggregate root (D109 commitment 1).

The gold set is a tenant-authored named container that aggregates
``GoldSetRevision`` value objects, each carrying an ordered list of
``GoldSetEntry`` value objects. The aggregate root carries identity
(``id`` + ``tenant_id`` + ``name`` unique per tenant) and a pointer
to the most recent finalized revision (``current_revision_id``);
revisions own the lifecycle (status, hash chain) and entries own the
authoring content (query plus expected chunk ID list).

Per D109's structural-precedent finding, the gold-set aggregate
mirrors the methodology/role aggregate shape from ``contexts/methodology/``
at the shape level (not the code-substrate level); the chain-self-
contained revision hash pattern is the same precedent that role
revisions use via ``padhanam.security.hash_chain.compute_revision_hash``.
S39 is Phase 1's first context to ship the full
create/append/finalize/list/get lifecycle with revision-granularity
hash-chain at application-layer granularity.

Domain code is framework-free per D16 — stdlib dataclasses only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class GoldSet:
    """Gold-set aggregate root.

    Immutable identity. The ``current_revision_id`` is nullable while
    no finalized revision exists; the create-gold-set use case
    inserts the aggregate plus an initial draft revision in a single
    transaction with the FK check deferred to commit time so the
    circular reference (gold_sets.current_revision_id → gold_set_revisions.id
    and gold_set_revisions.gold_set_id → gold_sets.id) is resolved
    cleanly without a placeholder-then-update pattern.
    """

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    name: str
    created_by_user_id: str
    created_at: datetime
    current_revision_id: UUID | None

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must be non-empty")
        if not self.name.strip():
            raise ValueError("name must be non-empty")
