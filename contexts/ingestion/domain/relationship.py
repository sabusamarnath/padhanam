"""Relationship value object — graph edge between two Entities (D64).

The extraction stage at S21 emits Relationships alongside Entities
(see ``entity.py``). Each Relationship carries a typed edge between
two Entities identified by their tenant-local composite key
``(name, entity_type)``; the relationship type itself comes from the
extraction prompt and is free-form per D64. Relationship uniqueness
is keyed on
``(tenant_id, source.name, source.entity_type, target.name,
target.entity_type, relationship_type, source_chunk_id)``;
the Neo4j adapter writes relationships via Cypher ``MERGE`` on the
same composite for idempotent re-extraction.

Frozen dataclass per D16 / D62. The Neo4j adapter owns the
impedance mismatch between Python identifiers and Cypher property
names; the domain stays pure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class EntityRef:
    """Endpoint identity for a Relationship.

    Within a tenant, an Entity is uniquely identified by
    ``(name, entity_type)`` per D64. ``EntityRef`` is the lightweight
    handle that carries that pair around without the full Entity
    aggregate (provenance, jurisdiction, created_at) which is
    redundant on a relationship endpoint.
    """

    name: str
    entity_type: str


@dataclass(frozen=True)
class Relationship:
    tenant_id: str
    jurisdiction: str
    source: EntityRef
    target: EntityRef
    relationship_type: str
    source_chunk_id: UUID
    created_at: datetime | None = None
