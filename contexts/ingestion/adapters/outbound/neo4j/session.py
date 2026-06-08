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
from dataclasses import replace
from datetime import datetime, timezone
from types import TracebackType
from typing import Sequence
from uuid import UUID

from neo4j import AsyncDriver, AsyncSession

from contexts.ingestion.domain.entity import Entity
from contexts.ingestion.domain.relationship import EntityRef, Relationship
from contexts.ingestion.ports.outcome_graph_port import (
    LeverEdgeRecord,
    OutcomeGraphRecord,
)
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

# Variable-length traversal from a named seed entity. The depth
# bound is interpolated into the path-pattern at format-time
# (Cypher does not parameterise path-length integers); the bound
# is validated by ``_validate_depth`` before substitution. The
# ``ANY(cid IN reachable.source_chunk_ids WHERE cid IN
# $indexed_chunk_ids)`` predicate carries the cross-track readiness
# filter D65 commits to: an entity surfaces only if at least one of
# its source chunks comes from a source whose pipeline reached
# ``indexed`` state. The set of indexed chunk_ids is computed by
# the adapter's pre-query against per-tenant Postgres and passed
# in as a parameter.
_TRAVERSE_FROM_SEED = """
MATCH path = (seed:Entity {{tenant_id: $tenant_id, name: $seed_name}})-[*0..{depth}]-(reachable:Entity)
WHERE reachable.tenant_id = $tenant_id
  AND ANY(cid IN reachable.source_chunk_ids WHERE cid IN $indexed_chunk_ids)
WITH reachable, length(path) AS plen, [r IN relationships(path) | type(r)] AS rel_path
ORDER BY plen ASC, reachable.name ASC
WITH reachable, head(collect({{plen: plen, rel_path: rel_path}})) AS shortest
RETURN reachable.tenant_id AS tenant_id,
       reachable.jurisdiction AS jurisdiction,
       reachable.name AS name,
       reachable.entity_type AS entity_type,
       reachable.source_chunk_ids AS source_chunk_ids,
       shortest.rel_path AS relationship_path,
       reachable.created_at AS created_at
ORDER BY size(shortest.rel_path) ASC, reachable.name ASC
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


# --- Goal-graph templates (D163, D163-clarification at S63) ----------------
# The whole-life goal taxonomy's typed shape: an :Outcome node, a thin :Lever
# reference node (the Postgres commitment by id, never a copy), and a LEVER_FOR
# edge. Per the D163 clarification (S63), the goal-level properties — mode, the
# level ladder, and the current target — live on the :Outcome node, not the
# edge: a goal has one mode and one target and may have many levers. The
# LEVER_FOR edge carries only that a lever serves the outcome. The LEVER_FOR
# type is a literal in the template (not dynamic), so Community-without-APOC
# composes it directly with no backtick substitution.
_MERGE_OUTCOME = """
MERGE (o:Outcome {tenant_id: $tenant_id, outcome_id: $outcome_id})
ON CREATE SET
    o.jurisdiction = $jurisdiction,
    o.created_at = $created_at
SET
    o.name = $name,
    o.control = $control,
    o.subject = $subject,
    o.mode = $mode,
    o.ladder = $ladder,
    o.current_target_level = $current_target_level,
    o.terminal_target = $terminal_target,
    o.terminal_state = $terminal_state
"""

# The LEVER_FOR edge carries only that a lever serves the outcome plus, for a
# sequence goal, the lever's own relationship-level attributes: step_order +
# step_state (which step, in what state). These are null for a single-lever
# progressive goal. Goal-level properties live on the :Outcome node.
_MERGE_LEVER_FOR_OUTCOME = """
MATCH (o:Outcome {tenant_id: $tenant_id, outcome_id: $outcome_id})
MERGE (l:Lever {tenant_id: $tenant_id, commitment_id: $commitment_id})
ON CREATE SET
    l.jurisdiction = $jurisdiction,
    l.created_at = $created_at
MERGE (l)-[r:LEVER_FOR {tenant_id: $tenant_id}]->(o)
ON CREATE SET
    r.jurisdiction = $jurisdiction,
    r.created_at = $created_at
SET
    r.step_order = $step_order,
    r.step_state = $step_state
"""

# The explicit raise (D9) now targets the :Outcome node — the current target is
# a goal-level property, so the raise no longer needs a lever id (the D163
# clarification's welcome simplification).
_SET_OUTCOME_TARGET = """
MATCH (o:Outcome {tenant_id: $tenant_id, outcome_id: $outcome_id})
SET o.current_target_level = $current_target_level
RETURN o.current_target_level AS current_target_level
"""

_LIST_OUTCOMES = """
MATCH (l:Lever {tenant_id: $tenant_id})
      -[r:LEVER_FOR {tenant_id: $tenant_id}]->
      (o:Outcome {tenant_id: $tenant_id})
RETURN o.outcome_id AS outcome_id,
       o.name AS name,
       o.control AS control,
       o.subject AS subject,
       o.mode AS mode,
       o.ladder AS ladder,
       o.current_target_level AS current_target_level,
       o.terminal_target AS terminal_target,
       o.terminal_state AS terminal_state,
       l.commitment_id AS commitment_id,
       r.step_order AS step_order,
       r.step_state AS step_state
ORDER BY o.name ASC, r.step_order ASC
"""


# Whitelist for relationship-type characters. Cypher backtick-
# quoting handles arbitrary strings inside identifiers, but the
# extraction prompt is constrained to ASCII identifier characters
# anyway and validating here narrows the surface for any future
# upstream-prompt drift. ``[A-Za-z_][A-Za-z0-9_]*`` matches the
# Cypher identifier shape.
_RELATIONSHIP_TYPE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# Variable-length path segments (e.g. ``[*0..3]``) require literal
# integers in Cypher; the wrapper interpolates the depth into the
# query template after validating it as a small non-negative
# integer. Arbitrary inputs cannot land in the format-substitution.
_MAX_TRAVERSE_DEPTH = 8


def _validate_relationship_type(relationship_type: str) -> None:
    if not _RELATIONSHIP_TYPE_RE.match(relationship_type):
        raise ValueError(
            f"relationship_type {relationship_type!r} is not a valid "
            "Cypher identifier; expected ^[A-Za-z_][A-Za-z0-9_]*$. "
            "The extraction prompt should produce identifier-shaped "
            "relationship types; the LiteLLM extractor adapter "
            "enforces this on output."
        )


def _validate_depth(depth: int) -> None:
    if not isinstance(depth, int) or isinstance(depth, bool):
        raise ValueError(f"depth must be int, got {type(depth).__name__}")
    if depth < 0:
        raise ValueError(f"depth must be non-negative, got {depth}")
    if depth > _MAX_TRAVERSE_DEPTH:
        raise ValueError(
            f"depth {depth} exceeds maximum {_MAX_TRAVERSE_DEPTH}; "
            "deeper traversals are out of Phase 1 scope"
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

    async def traverse_from_seed(
        self,
        seed_name: str,
        depth: int,
        indexed_chunk_ids: Sequence[UUID],
    ) -> Sequence[dict[str, object]]:
        """Variable-length traversal from a seed entity (D65).

        Returns one row per reachable entity within ``depth`` hops,
        deduplicated to the shortest path. The cross-track readiness
        filter is enforced via the ``indexed_chunk_ids`` parameter:
        an entity surfaces only if at least one of its
        ``source_chunk_ids`` is in the set. The seed itself surfaces
        with an empty relationship_path when its own source chunks
        meet the readiness predicate.

        Returns raw Cypher row dicts (not ``EntityResult`` value
        objects) because the wrapper's job is the Cypher boundary,
        not the domain shape — the adapter at
        ``Neo4jTraverse.traverse_graph`` does the domain mapping.
        """
        _validate_depth(depth)
        if not indexed_chunk_ids:
            # No indexed sources for this tenant ⇒ the readiness
            # predicate excludes everything; short-circuit before
            # the Cypher query.
            return []
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "seed_name": seed_name,
            "indexed_chunk_ids": [str(cid) for cid in indexed_chunk_ids],
        }
        cypher = _TRAVERSE_FROM_SEED.format(depth=depth)
        result = await session.run(cypher, params)
        records = await result.data()
        return list(records)

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


    async def merge_outcome(
        self,
        *,
        outcome_id: UUID,
        name: str,
        control: str,
        subject: str,
        mode: str,
        ladder: Sequence[str],
        current_target_level: str | None,
        terminal_target: str | None = None,
        terminal_state: str | None = None,
    ) -> None:
        """MERGE an :Outcome node bound to the session's tenant (D163).

        Per the D163 clarification (S63), the goal-level properties live on the
        node: mode, the level ladder and current target (progressive), and the
        terminal target + state (sequence). The unused shape's properties are
        ``None``.
        """
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "jurisdiction": self._jurisdiction,
            "outcome_id": str(outcome_id),
            "name": name,
            "control": control,
            "subject": subject,
            "mode": mode,
            "ladder": list(ladder),
            "current_target_level": current_target_level,
            "terminal_target": terminal_target,
            "terminal_state": terminal_state,
            "created_at": _now_utc(),
        }
        await session.run(_MERGE_OUTCOME, params)

    async def merge_lever_for_outcome(
        self,
        *,
        outcome_id: UUID,
        commitment_id: UUID,
        step_order: int | None = None,
        step_state: str | None = None,
    ) -> None:
        """MERGE the :Lever node + the LEVER_FOR edge to the Outcome (D163).

        The edge carries only that the lever serves the outcome plus, for a
        sequence goal, the lever's relationship-level ``step_order`` +
        ``step_state`` (the D163 clarification). Goal-level properties live on
        the :Outcome node.
        """
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "jurisdiction": self._jurisdiction,
            "outcome_id": str(outcome_id),
            "commitment_id": str(commitment_id),
            "step_order": step_order,
            "step_state": step_state,
            "created_at": _now_utc(),
        }
        await session.run(_MERGE_LEVER_FOR_OUTCOME, params)

    async def set_outcome_target(
        self,
        *,
        outcome_id: UUID,
        current_target_level: str,
    ) -> str | None:
        """Set the :Outcome node's current_target_level (the explicit raise, D9).

        The target is a goal-level property (D163 clarification), so the raise
        no longer needs a lever id.
        """
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "outcome_id": str(outcome_id),
            "current_target_level": current_target_level,
        }
        result = await session.run(_SET_OUTCOME_TARGET, params)
        record = await result.single()
        if record is None:
            return None
        return record["current_target_level"]

    async def list_outcomes(self) -> Sequence[OutcomeGraphRecord]:
        """Return every Outcome with its lever edges for the bound tenant (D163).

        One Cypher row per (outcome, lever); progressive goals have one lever,
        sequence goals have many. Rows are aggregated here into one
        ``OutcomeGraphRecord`` per outcome carrying a tuple of lever-edge
        records — the wrapper owns the Cypher boundary, so the aggregation
        stays on this side of the fence.
        """
        session = self._bound_session
        params = {"tenant_id": self._tenant_id}
        result = await session.run(_LIST_OUTCOMES, params)
        rows = await result.data()
        by_outcome: dict[str, OutcomeGraphRecord] = {}
        order: list[str] = []
        for row in rows:
            oid = row["outcome_id"]
            lever = LeverEdgeRecord(
                commitment_id=UUID(row["commitment_id"]),
                step_order=row["step_order"],
                step_state=row["step_state"],
            )
            if oid not in by_outcome:
                order.append(oid)
                by_outcome[oid] = OutcomeGraphRecord(
                    outcome_id=UUID(oid),
                    name=row["name"],
                    control=row["control"],
                    subject=row["subject"],
                    mode=row["mode"],
                    ladder=tuple(row["ladder"] or ()),
                    current_target_level=row["current_target_level"],
                    terminal_target=row["terminal_target"],
                    terminal_state=row["terminal_state"],
                    levers=(lever,),
                )
            else:
                existing = by_outcome[oid]
                by_outcome[oid] = replace(
                    existing, levers=existing.levers + (lever,)
                )
        return [by_outcome[oid] for oid in order]


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
