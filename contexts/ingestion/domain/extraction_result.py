"""ExtractionResult — the EntityExtractorPort return shape (D64).

Carries the entities and relationships an extraction call produces
for a sequence of input chunks. The ``GraphRepository`` adapter
writes both via Cypher MERGE on the per-shape composite uniqueness
keys per D64; re-running extraction over the same chunks produces
no duplicate nodes or edges.

Frozen dataclass per D16 / D62. Sequences are tuples by default so
the value is hashable and immutable; callers that pass lists keep
ownership of their lists, the adapter materialises into a tuple
via ``tuple(...)`` at construction time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from contexts.ingestion.domain.entity import Entity
from contexts.ingestion.domain.relationship import Relationship


@dataclass(frozen=True)
class ExtractionResult:
    entities: Sequence[Entity] = field(default_factory=tuple)
    relationships: Sequence[Relationship] = field(default_factory=tuple)
