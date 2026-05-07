"""Tenant-scoped Neo4j session wrapper (D63).

The single Cypher-execution surface that exposes the shared Neo4j
instance to the rest of the codebase. Every method's Cypher
template auto-binds the ``$tenant_id`` predicate from the bound
``TenantContext``, so missing-predicate Cypher cannot exist in
callable code. Raw ``neo4j.AsyncDriver.session()`` and ``tx.run()``
calls live only in this module; the ``neo4j-confined`` import-
linter contract plus the AST enforcement test at
``tests/_enforcement/test_no_raw_neo4j_session.py`` fence the
boundary mechanically.

The wrapper is a context manager so each call site opens and closes
a Neo4j session deterministically, mirroring SQLAlchemy
``async_sessionmaker`` usage in the Postgres adapter. The driver
itself is shared (one driver per process); each tenant-scoped
operation constructs a fresh session against the driver.

Schema invariant per D64: every Entity and Relationship written
through this wrapper carries ``tenant_id`` matching the bound
context. Reads filter by the same ``tenant_id`` predicate. The
pattern guarantees property-based tenant isolation under the
wrapper's API surface, which the tenant-isolation contract test
at ``tests/contract/tenant_isolation/test_neo4j_isolation.py``
red-team-verifies on both reads and writes.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from types import TracebackType
from typing import Sequence
from uuid import UUID

from neo4j import AsyncDriver, AsyncSession

from contexts.ingestion.domain.entity import Entity
from contexts.ingestion.domain.relationship import EntityRef, Relationship
from shared_kernel import TenantContext


# Cypher templates. The wrapper composes ``$tenant_id`` from the
# bound context into every parameter map, so the templates carry
# ``$tenant_id`` literally and the wrapper never accepts a
# ``tenant_id`` argument from outside.
_MERGE_ENTITY = """
MERGE (e:Entity {tenant_id: $tenant_id, name: $name, entity_type: $entity_type})
ON CREATE SET
    e.jurisdiction = $jurisdiction,
    e.source_chunk_ids = $source_chunk_ids,
    e.created_at = $created_at
ON MATCH SET
    e.source_chunk_ids = [cid IN coalesce(e.source_chunk_ids, []) WHERE NOT cid IN $source_chunk_ids] + $source_chunk_ids
"""

# Neo4j Community ships without APOC, so the relationship type is
# composed into the Cypher template as a backtick-quoted identifier.
# ``_validate_relationship_type`` whitelists the input to a strict
# Cypher-identifier shape before the format-substitution, narrowing
# the surface even though backticks would tolerate arbitrary text.
_MERGE_RELATIONSHIP = """
MATCH (s:Entity {{tenant_id: $tenant_id, name: $source_name, entity_type: $source_entity_type}})
MATCH (t:Entity {{tenant_id: $tenant_id, name: $target_name, entity_type: $target_entity_type}})
MERGE (s)-[r:`{relationship_type}` {{tenant_id: $tenant_id, source_chunk_id: $source_chunk_id}}]->(t)
ON CREATE SET
    r.jurisdiction = $jurisdiction,
    r.created_at = $created_at
"""

_GET_ENTITIES_BY_CHUNK_IDS = """
MATCH (e:Entity)
WHERE e.tenant_id = $tenant_id
  AND ANY(cid IN e.source_chunk_ids WHERE cid IN $chunk_ids)
RETURN e.tenant_id AS tenant_id,
       e.jurisdiction AS jurisdiction,
       e.name AS name,
       e.entity_type AS entity_type,
       e.source_chunk_ids AS source_chunk_ids,
       e.created_at AS created_at
"""

_GET_RELATIONSHIPS_BY_CHUNK_IDS = """
MATCH (s:Entity)-[r]->(t:Entity)
WHERE r.tenant_id = $tenant_id
  AND r.source_chunk_id IN $chunk_ids
RETURN r.tenant_id AS tenant_id,
       r.jurisdiction AS jurisdiction,
       s.name AS source_name,
       s.entity_type AS source_entity_type,
       t.name AS target_name,
       t.entity_type AS target_entity_type,
       type(r) AS relationship_type,
       r.source_chunk_id AS source_chunk_id,
       r.created_at AS created_at
"""


# Whitelist for relationship-type characters. Cypher backtick-
# quoting handles arbitrary strings inside identifiers, but the
# extraction prompt is constrained to ASCII identifier characters
# anyway and validating here narrows the surface for any future
# upstream-prompt drift. ``[A-Za-z_][A-Za-z0-9_]*`` matches the
# Cypher identifier shape.
_RELATIONSHIP_TYPE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_relationship_type(relationship_type: str) -> None:
    if not _RELATIONSHIP_TYPE_RE.match(relationship_type):
        raise ValueError(
            f"relationship_type {relationship_type!r} is not a valid "
            "Cypher identifier; expected ^[A-Za-z_][A-Za-z0-9_]*$. "
            "The extraction prompt should produce identifier-shaped "
            "relationship types; the LiteLLM extractor adapter "
            "enforces this on output."
        )


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


class TenantScopedNeo4jSession:
    """Tenant-scoped Cypher execution surface (D63).

    Construct with a driver and a TenantContext; every method
    auto-binds the bound tenant_id into its Cypher parameter map.
    Use as an async context manager so the underlying Neo4j
    session is opened and closed deterministically.
    """

    def __init__(self, driver: AsyncDriver, tenant_context: TenantContext) -> None:
        self._driver = driver
        self._tenant_id = tenant_context.tenant_id
        self._jurisdiction = tenant_context.jurisdiction
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "TenantScopedNeo4jSession":
        self._session = self._driver.session()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    @property
    def _bound_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError(
                "TenantScopedNeo4jSession used outside `async with` block; "
                "session is not bound. Open as `async with session:` and "
                "use within the context."
            )
        return self._session

    async def merge_entities(self, entities: Sequence[Entity]) -> None:
        if not entities:
            return
        session = self._bound_session
        for entity in entities:
            if entity.tenant_id != self._tenant_id:
                raise ValueError(
                    f"Entity tenant_id {entity.tenant_id!r} does not match "
                    f"bound tenant {self._tenant_id!r}; the wrapper refuses "
                    "to write cross-tenant data."
                )
            params = {
                "tenant_id": self._tenant_id,
                "jurisdiction": entity.jurisdiction,
                "name": entity.name,
                "entity_type": entity.entity_type,
                "source_chunk_ids": [str(cid) for cid in entity.source_chunk_ids],
                "created_at": entity.created_at or _now_utc(),
            }
            await session.run(_MERGE_ENTITY, params)

    async def merge_relationships(
        self, relationships: Sequence[Relationship]
    ) -> None:
        if not relationships:
            return
        session = self._bound_session
        for rel in relationships:
            if rel.tenant_id != self._tenant_id:
                raise ValueError(
                    f"Relationship tenant_id {rel.tenant_id!r} does not "
                    f"match bound tenant {self._tenant_id!r}; the wrapper "
                    "refuses to write cross-tenant data."
                )
            _validate_relationship_type(rel.relationship_type)
            params = {
                "tenant_id": self._tenant_id,
                "jurisdiction": rel.jurisdiction,
                "source_name": rel.source.name,
                "source_entity_type": rel.source.entity_type,
                "target_name": rel.target.name,
                "target_entity_type": rel.target.entity_type,
                "source_chunk_id": str(rel.source_chunk_id),
                "created_at": rel.created_at or _now_utc(),
            }
            cypher = _MERGE_RELATIONSHIP.format(
                relationship_type=rel.relationship_type
            )
            await session.run(cypher, params)

    async def get_entities_by_chunk_ids(
        self, chunk_ids: Sequence[UUID]
    ) -> Sequence[Entity]:
        if not chunk_ids:
            return []
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "chunk_ids": [str(cid) for cid in chunk_ids],
        }
        result = await session.run(_GET_ENTITIES_BY_CHUNK_IDS, params)
        records = await result.data()
        return [
            Entity(
                tenant_id=row["tenant_id"],
                jurisdiction=row["jurisdiction"],
                name=row["name"],
                entity_type=row["entity_type"],
                source_chunk_ids=tuple(UUID(cid) for cid in row["source_chunk_ids"]),
                created_at=_to_python_datetime(row["created_at"]),
            )
            for row in records
        ]

    async def get_relationships_by_chunk_ids(
        self, chunk_ids: Sequence[UUID]
    ) -> Sequence[Relationship]:
        if not chunk_ids:
            return []
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "chunk_ids": [str(cid) for cid in chunk_ids],
        }
        result = await session.run(_GET_RELATIONSHIPS_BY_CHUNK_IDS, params)
        records = await result.data()
        return [
            Relationship(
                tenant_id=row["tenant_id"],
                jurisdiction=row["jurisdiction"],
                source=EntityRef(
                    name=row["source_name"],
                    entity_type=row["source_entity_type"],
                ),
                target=EntityRef(
                    name=row["target_name"],
                    entity_type=row["target_entity_type"],
                ),
                relationship_type=row["relationship_type"],
                source_chunk_id=UUID(row["source_chunk_id"]),
                created_at=_to_python_datetime(row["created_at"]),
            )
            for row in records
        ]


def _to_python_datetime(value: object) -> datetime | None:
    """The Neo4j driver returns its own ``DateTime`` subclass for
    temporal values. ``to_native()`` converts to a stdlib
    ``datetime``; ``None`` passes through.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    to_native = getattr(value, "to_native", None)
    if to_native is not None:
        return to_native()
    raise TypeError(f"unexpected datetime shape from neo4j driver: {value!r}")
