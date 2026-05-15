"""Gold-set entry value object (D109 commitment 3).

The entry is one (query, ordered expected chunk IDs) pair within a
gold-set revision. ``entry_index`` preserves position within the
revision so the runner at S40 can iterate in the operator-authored
order; ``expected_chunk_ids`` order encodes ranked relevance per
D105's seventh commitment (the array order is what recall@k,
precision@k, and MRR read at metric-computation time).

Per D109 commitment 3 the ``expected_chunk_ids`` array references
chunk IDs from the per-tenant chunks table in
``contexts/ingestion/``; no foreign key is enforced at the database
level because chunk lifecycle is independent of gold-set authoring.

Domain code is framework-free per D16 — stdlib dataclasses only.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GoldSetEntry:
    """One entry in a gold-set revision.

    Immutable per D31; corrections happen by appending the next entry
    or by opening a new revision, never by mutating an existing entry.
    """

    id: UUID
    gold_set_revision_id: UUID
    entry_index: int
    query: str
    expected_chunk_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        if self.entry_index < 0:
            raise ValueError(
                f"entry_index must be non-negative, got {self.entry_index}"
            )
        if not self.query.strip():
            raise ValueError("query must be non-empty")
        if not self.expected_chunk_ids:
            raise ValueError(
                "expected_chunk_ids must carry at least one chunk reference"
            )
