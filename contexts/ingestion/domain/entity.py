"""Entity aggregate — graph node value (D64).

The extraction stage at S21 emits Entities and Relationships (see
``relationship.py``) from parsed chunks. Entity uniqueness within a
tenant is keyed on the composite ``(tenant_id, name, entity_type)``
per D64; the Neo4j adapter writes entities via Cypher ``MERGE`` on
the same composite for idempotent re-extraction.

Frozen dataclass per D16 / D62. The Neo4j adapter owns the
impedance mismatch between Python identifiers and Cypher property
names; the domain stays pure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence
from uuid import UUID


@dataclass(frozen=True)
class Entity:
    tenant_id: str
    jurisdiction: str
    name: str
    entity_type: str
    source_chunk_ids: Sequence[UUID] = field(default_factory=tuple)
    created_at: datetime | None = None
