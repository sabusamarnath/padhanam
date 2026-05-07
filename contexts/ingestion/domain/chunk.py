"""Chunk value object — the parsed-content row (D60 / D61).

Each Source produces zero or more Chunks at the parsing stage. The
Chunk carries the parsed text plus structural metadata the parser
emitted (heading hierarchy for markdown, paragraph index for plain
text). Embedding columns land at S20; extraction-edge references
land at S21.

structural_metadata is a Mapping at the domain layer; the adapter
serialises to jsonb. Frozen dataclass per D16. The
``(source_id, chunk_index)`` pair is the natural identity at the
domain level — UUIDs come from the database default and the
unique constraint at the adapter layer is the structural backstop
for the worker idempotency contract per D60.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping
from uuid import UUID


@dataclass(frozen=True)
class Chunk:
    id: UUID
    source_id: UUID
    tenant_id: str
    jurisdiction: str
    chunk_index: int
    content: str
    structural_metadata: Mapping[str, object] = field(default_factory=dict)
    created_at: datetime | None = None
