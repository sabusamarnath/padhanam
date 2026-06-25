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
    AuthoredCddRecord,
    AuthoredEdgeRecord,
    AuthoredElementRecord,
    LeverEdgeRecord,
    OutcomeGraphRecord,
)
from contexts.ingestion.ports.unit_graph_port import (
    ElementEvidenceRecord,
    ElementEvidenceWrite,
    FacetLinkRecord,
    GoalEdgeRecord,
    GoalEdgeWrite,
    UnitGraphRecord,
    UnitWrite,
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
    o.terminal_state = $terminal_state,
    o.aliases = $aliases,
    o.domain = $domain
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

# The reversible archive (S103e, D205): mark a goal archived without deleting it
# (the no-auto-deletion invariant + originals-never-erased — a user-initiated
# removal marks, never erases). The node, its authored CDD elements, its
# EVIDENCES binds and audit history all stay intact; only the marker is set.
# _UNARCHIVE removes the marker so the goal returns whole to every read.
_ARCHIVE_OUTCOME = """
MATCH (o:Outcome {tenant_id: $tenant_id, outcome_id: $outcome_id})
SET o.archived_at = $archived_at
RETURN o.outcome_id AS outcome_id
"""

_UNARCHIVE_OUTCOME = """
MATCH (o:Outcome {tenant_id: $tenant_id, outcome_id: $outcome_id})
REMOVE o.archived_at
RETURN o.outcome_id AS outcome_id
"""

# The archived set — the complement of _LIST_OUTCOMES (which scopes to active).
# Reactivation reads this directly rather than guessing ids from seed modules, so
# it cannot drift from what is actually archived.
_LIST_ARCHIVED_OUTCOME_IDS = """
MATCH (o:Outcome {tenant_id: $tenant_id})
WHERE o.archived_at IS NOT NULL
RETURN o.outcome_id AS outcome_id
ORDER BY o.outcome_id ASC
"""

# The archive marker (S103e, D205): a goal the user has archived carries
# o.archived_at; the list scopes to active goals (archived_at IS NULL), so an
# archived goal drops out of the assess surface and the matcher (both read this
# via list_goals) without being deleted. A goal that has never been archived has
# no such property, and `IS NULL` is true for the missing property, so existing
# goals pass unchanged. Reversible: _UNARCHIVE_OUTCOME removes the marker.
_LIST_OUTCOMES = """
MATCH (l:Lever {tenant_id: $tenant_id})
      -[r:LEVER_FOR {tenant_id: $tenant_id}]->
      (o:Outcome {tenant_id: $tenant_id})
WHERE o.archived_at IS NULL
RETURN o.outcome_id AS outcome_id,
       o.name AS name,
       o.control AS control,
       o.subject AS subject,
       o.mode AS mode,
       o.ladder AS ladder,
       o.current_target_level AS current_target_level,
       o.terminal_target AS terminal_target,
       o.terminal_state AS terminal_state,
       o.aliases AS aliases,
       o.domain AS domain,
       l.commitment_id AS commitment_id,
       r.step_order AS step_order,
       r.step_state AS step_state
ORDER BY o.name ASC, r.step_order ASC
"""


# --- Authored CDD templates (S102, D200) -----------------------------------
# The authored layer: the LLM drafts each goal's levers, intermediaries,
# externals, and authored causal edges, the user proofs. Distinct from the
# matcher's derived SERVES/LEVER_FOR. Neo4j node labels and relationship types
# are not parameterisable, so the wrapper composes the literal label/type from a
# whitelist (kind -> (label, id_property)); the whitelist keeps it injection-safe
# (the LEVER_FOR-literal precedent). An authored :Lever identifies by lever_id
# (commitment_id stays the matcher lever's key); :Intermediary / :External
# identify by element_id; the :Outcome (an edge endpoint only) by outcome_id.
_AUTHORED_NODE = {
    "lever": ("Lever", "lever_id"),
    "intermediary": ("Intermediary", "element_id"),
    "external": ("External", "element_id"),
}
# Edge endpoints additionally allow the outcome node and, for gate-local CDDs
# (S103g, D207), the :Gate node as the local-outcome endpoint (parallel to
# :Outcome for the goal — an intermediary FEEDS its gate).
_AUTHORED_ENDPOINT = {
    **_AUTHORED_NODE,
    "outcome": ("Outcome", "outcome_id"),
    "gate": ("Gate", "gate_id"),
}
_AUTHORED_EDGE_TYPES = frozenset({"FEEDS", "INFLUENCES"})


def _required_edge_type(kind: str) -> str:
    """The edge type an element of this kind uses as a source (D198/D201): an
    external INFLUENCES (it is not controlled); a lever/intermediary FEEDS. Used
    by the reclassify flagger to detect now-ungrammatical incident edges."""
    return "INFLUENCES" if kind == "external" else "FEEDS"


def _authored_node(kind: str) -> tuple[str, str]:
    try:
        return _AUTHORED_NODE[kind]
    except KeyError:
        raise ValueError(f"unknown authored element kind: {kind!r}") from None


def _authored_endpoint(kind: str) -> tuple[str, str]:
    try:
        return _AUTHORED_ENDPOINT[kind]
    except KeyError:
        raise ValueError(f"unknown authored endpoint kind: {kind!r}") from None


def _merge_authored_element_cypher(label: str, id_prop: str) -> str:
    return f"""
MERGE (n:{label} {{tenant_id: $tenant_id, {id_prop}: $element_id}})
ON CREATE SET
    n.jurisdiction = $jurisdiction,
    n.created_at = $created_at
SET
    n.outcome_id = $outcome_id,
    n.gate_id = $gate_id,
    n.label = $label,
    n.provenance_origin = $provenance_origin,
    n.proof_state = $proof_state
"""


def _merge_authored_edge_cypher(
    edge_type: str, slabel: str, sid: str, tlabel: str, tid: str
) -> str:
    return f"""
MATCH (s:{slabel} {{tenant_id: $tenant_id, {sid}: $source_id}})
MATCH (t:{tlabel} {{tenant_id: $tenant_id, {tid}: $target_id}})
MERGE (s)-[r:{edge_type} {{tenant_id: $tenant_id}}]->(t)
ON CREATE SET
    r.jurisdiction = $jurisdiction,
    r.created_at = $created_at
"""


def _delete_authored_edge_cypher(
    edge_type: str, slabel: str, sid: str, tlabel: str, tid: str
) -> str:
    """Delete one authored edge by its endpoints (S103g, D207 — used to migrate a
    relocated element's edge: drop the old goal-level FEEDS, add the gate one)."""
    return f"""
MATCH (s:{slabel} {{tenant_id: $tenant_id, {sid}: $source_id}})
      -[r:{edge_type} {{tenant_id: $tenant_id}}]->
      (t:{tlabel} {{tenant_id: $tenant_id, {tid}: $target_id}})
DELETE r
"""


def _set_element_gate_cypher(label: str, id_prop: str) -> str:
    """Relocate an authored element into a gate (S103g, D207): set its gate_id,
    preserving the node, its label, and its provenance (the relocation carries the
    live provenance — it is not a re-authoring). Returns the id on match."""
    return f"""
MATCH (n:{label} {{tenant_id: $tenant_id, {id_prop}: $element_id}})
SET n.gate_id = $gate_id
RETURN n.{id_prop} AS element_id
"""


def _set_authored_proof_state_cypher(label: str, id_prop: str) -> str:
    return f"""
MATCH (n:{label} {{tenant_id: $tenant_id, {id_prop}: $element_id}})
SET n.proof_state = $proof_state
RETURN n.{id_prop} AS element_id
"""


def _set_authored_label_cypher(label: str, id_prop: str) -> str:
    return f"""
MATCH (n:{label} {{tenant_id: $tenant_id, {id_prop}: $element_id}})
SET n.label = $label,
    n.provenance_origin = 'user_authored'
RETURN n.{id_prop} AS element_id
"""


def _delete_authored_element_cypher(label: str, id_prop: str) -> str:
    # Deletion is detected from the result summary's nodes_deleted counter, so
    # no RETURN is needed (a no-match MATCH simply deletes nothing).
    return f"""
MATCH (n:{label} {{tenant_id: $tenant_id, {id_prop}: $element_id}})
DETACH DELETE n
"""


def _reclassify_authored_element_cypher(
    from_label: str,
    from_idprop: str,
    to_label: str,
    to_idprop: str,
    *,
    drop_commitment: bool,
) -> str:
    """Swap an authored element's type-label, preserving the node and its stable
    id (D201, S103a). The label swap also flips provenance_origin to
    user_authored (the correction signal). When the kinds key by different id
    properties (lever's lever_id vs intermediary/external's element_id), the id
    value moves between them so the new kind's read finds the node; the SET reads
    the old property before the REMOVE drops it. Leaving the lever kind drops the
    lever-only commitment_id. RETURN detects success (no row = absent/cross-tenant).
    """
    set_parts = [f"n:{to_label}", "n.provenance_origin = 'user_authored'"]
    remove_parts = [f"n:{from_label}"]
    if from_idprop != to_idprop:
        set_parts.append(f"n.{to_idprop} = n.{from_idprop}")
        remove_parts.append(f"n.{from_idprop}")
    if drop_commitment:
        remove_parts.append("n.commitment_id")
    return f"""
MATCH (n:{from_label} {{tenant_id: $tenant_id, {from_idprop}: $element_id}})
SET {", ".join(set_parts)}
REMOVE {", ".join(remove_parts)}
RETURN n.{to_idprop} AS element_id
"""


def _flag_reclassified_edges_cypher(to_label: str, to_idprop: str) -> str:
    """Flag (never drop) the reclassified node's outgoing authored edges whose
    type no longer fits the new kind (D201): an external INFLUENCES, a
    lever/intermediary FEEDS. The id value is preserved by the swap, so the same
    ``$element_id`` matches the node under its new id property."""
    return f"""
MATCH (n:{to_label} {{tenant_id: $tenant_id, {to_idprop}: $element_id}})
      -[r:FEEDS|INFLUENCES {{tenant_id: $tenant_id}}]->()
WHERE type(r) <> $required_type
SET r.needs_review = true
"""


# Read a goal's authored elements (each kind keyed by its own id property) and
# the authored causal edges within the goal's CDD. Every authored node carries
# outcome_id = the goal, so the edge read scopes by either endpoint's outcome_id.
_LIST_AUTHORED_LEVERS = """
MATCH (n:Lever {tenant_id: $tenant_id, outcome_id: $outcome_id})
WHERE n.lever_id IS NOT NULL
RETURN n.lever_id AS element_id, n.label AS label,
       n.provenance_origin AS provenance_origin, n.proof_state AS proof_state,
       n.gate_id AS gate_id
ORDER BY n.label ASC
"""
_LIST_AUTHORED_INTERMEDIARIES = """
MATCH (n:Intermediary {tenant_id: $tenant_id, outcome_id: $outcome_id})
RETURN n.element_id AS element_id, n.label AS label,
       n.provenance_origin AS provenance_origin, n.proof_state AS proof_state,
       n.gate_id AS gate_id
ORDER BY n.label ASC
"""
_LIST_AUTHORED_EXTERNALS = """
MATCH (n:External {tenant_id: $tenant_id, outcome_id: $outcome_id})
RETURN n.element_id AS element_id, n.label AS label,
       n.provenance_origin AS provenance_origin, n.proof_state AS proof_state,
       n.gate_id AS gate_id
ORDER BY n.label ASC
"""
# The coalesce includes gate_id before outcome_id so the :Gate node (the
# local-outcome endpoint, which carries both gate_id and outcome_id) resolves to
# its gate_id; the :Outcome goal node (no gate_id) still resolves to outcome_id,
# and gate-scoped elements resolve to their own lever_id/element_id (gate_id is a
# scoping property on them, not their identity).
_LIST_AUTHORED_EDGES = """
MATCH (s)-[r:FEEDS|INFLUENCES {tenant_id: $tenant_id}]->(t)
WHERE s.outcome_id = $outcome_id OR t.outcome_id = $outcome_id
RETURN type(r) AS edge_type,
       labels(s)[0] AS source_kind,
       coalesce(s.lever_id, s.element_id, s.gate_id, s.outcome_id) AS source_id,
       labels(t)[0] AS target_kind,
       coalesce(t.lever_id, t.element_id, t.gate_id, t.outcome_id) AS target_id,
       coalesce(r.needs_review, false) AS needs_review
"""

# --- Process gates (S103g, D207) -------------------------------------------
# A gate is a first-class flow node, sequenced by gate_order, scoped to the goal
# by outcome_id, referencing a D163 step where one corresponds. The gate node is
# the local-outcome endpoint of its CDD (an intermediary FEEDS the gate). Merged
# idempotently by (tenant_id, gate_id) — the 0007 uniqueness constraint.
_MERGE_GATE = """
MERGE (g:Gate {tenant_id: $tenant_id, gate_id: $gate_id})
ON CREATE SET
    g.jurisdiction = $jurisdiction,
    g.created_at = $created_at
SET
    g.outcome_id = $outcome_id,
    g.name = $name,
    g.gate_order = $gate_order,
    g.local_outcome = $local_outcome,
    g.local_goal = $local_goal,
    g.provenance_origin = $provenance_origin,
    g.proof_state = $proof_state,
    g.step_commitment_id = $step_commitment_id
"""
_LIST_GATES = """
MATCH (g:Gate {tenant_id: $tenant_id, outcome_id: $outcome_id})
RETURN g.gate_id AS gate_id, g.name AS name, g.gate_order AS gate_order,
       g.local_outcome AS local_outcome, g.local_goal AS local_goal,
       g.provenance_origin AS provenance_origin, g.proof_state AS proof_state,
       g.step_commitment_id AS step_commitment_id
ORDER BY g.gate_order ASC
"""

# --- Process instances / opportunities (S103h, D208) -----------------------
# An opportunity is a Flow item belonging to the goal (outcome_id), positioned at
# its furthest-evidenced gate (current_gate_id), grouping its units (BELONGS_TO).
_MERGE_OPPORTUNITY = """
MERGE (o:Opportunity {tenant_id: $tenant_id, opportunity_id: $opportunity_id})
ON CREATE SET
    o.jurisdiction = $jurisdiction,
    o.created_at = $created_at
SET
    o.outcome_id = $outcome_id,
    o.name = $name,
    o.current_gate_id = $current_gate_id,
    o.provenance_origin = $provenance_origin,
    o.proof_state = $proof_state,
    o.source = $source
"""
_LIST_OPPORTUNITIES = """
MATCH (o:Opportunity {tenant_id: $tenant_id, outcome_id: $outcome_id})
OPTIONAL MATCH (u:Unit {tenant_id: $tenant_id})-[:BELONGS_TO {tenant_id: $tenant_id}]->(o)
RETURN o.opportunity_id AS opportunity_id, o.name AS name,
       o.current_gate_id AS current_gate_id,
       o.provenance_origin AS provenance_origin, o.proof_state AS proof_state,
       o.source AS source, count(u) AS unit_count
ORDER BY o.name ASC
"""
# Idempotent membership: MERGE the BELONGS_TO edge keyed on (unit, opportunity).
_ATTACH_UNIT_TO_OPPORTUNITY = """
MATCH (u:Unit {tenant_id: $tenant_id, unit_id: $unit_id})
MATCH (o:Opportunity {tenant_id: $tenant_id, opportunity_id: $opportunity_id})
MERGE (u)-[r:BELONGS_TO {tenant_id: $tenant_id}]->(o)
ON CREATE SET r.jurisdiction = $jurisdiction, r.created_at = $created_at
"""
# Clear an opportunity's memberships so a re-instantiation reconciles cleanly.
_CLEAR_OPPORTUNITY_UNITS = """
MATCH (:Unit {tenant_id: $tenant_id})
      -[r:BELONGS_TO {tenant_id: $tenant_id}]->
      (o:Opportunity {tenant_id: $tenant_id, opportunity_id: $opportunity_id})
DELETE r
"""

# The authored stance on the outcome — the measurable result that means the goal
# is met (D200), stored on the existing :Outcome node (D199's two faces). S103a
# makes it proofable: it carries an origin + proof_state alongside the text, all
# schemaless (no constraint, no migration). Reject clears all three; the node
# itself (the goal) is never deleted.
_SET_AUTHORED_OUTCOME = """
MATCH (o:Outcome {tenant_id: $tenant_id, outcome_id: $outcome_id})
SET o.authored_expected_outcome = $expected_outcome,
    o.authored_outcome_origin = $provenance_origin,
    o.authored_outcome_proof_state = $proof_state
RETURN o.outcome_id AS outcome_id
"""
_READ_AUTHORED_OUTCOME = """
MATCH (o:Outcome {tenant_id: $tenant_id, outcome_id: $outcome_id})
RETURN o.authored_expected_outcome AS expected_outcome,
       o.authored_outcome_origin AS provenance_origin,
       o.authored_outcome_proof_state AS proof_state,
       o.disposition_moat AS disposition_moat,
       o.disposition_pipeline AS disposition_pipeline,
       o.disposition_market AS disposition_market,
       o.disposition_parked AS disposition_parked
"""

# S103j (D210): the precision pass's disposition counts (S103i), persisted on the
# goal so the Map's recommendation-shaped summary reads them — schemaless, set
# each correlate (derived state, D155). No migration.
_SET_OUTCOME_DISPOSITION = """
MATCH (o:Outcome {tenant_id: $tenant_id, outcome_id: $outcome_id})
SET o.disposition_moat = $moat,
    o.disposition_pipeline = $pipeline,
    o.disposition_market = $market,
    o.disposition_parked = $parked
RETURN o.outcome_id AS outcome_id
"""
_ACCEPT_AUTHORED_OUTCOME = """
MATCH (o:Outcome {tenant_id: $tenant_id, outcome_id: $outcome_id})
WHERE o.authored_expected_outcome IS NOT NULL
SET o.authored_outcome_proof_state = 'accepted'
RETURN o.outcome_id AS outcome_id
"""
_CLEAR_AUTHORED_OUTCOME = """
MATCH (o:Outcome {tenant_id: $tenant_id, outcome_id: $outcome_id})
WHERE o.authored_expected_outcome IS NOT NULL
REMOVE o.authored_expected_outcome,
       o.authored_outcome_origin,
       o.authored_outcome_proof_state
RETURN o.outcome_id AS outcome_id
"""


# --- Work-unit templates (D168, D166) --------------------------------------
# The plan-side work-unit correlation: a :Unit anchor node, a thin :Facet
# reference node per facet (id only, never a copy of the cache row — the :Lever
# rule), and a SAME_WORK edge carrying the title-and-time inference's confidence,
# status, and basis. Correlation is derived state (D155): each run deletes the
# tenant's facets + edges and prunes stale units, then re-merges, preserving
# :Unit nodes whose deterministic id persists (so P19's goal edge survives).
_DELETE_FACETS = """
MATCH (f:Facet {tenant_id: $tenant_id})
DETACH DELETE f
"""

# Prune :Unit nodes for the tenant no longer in the recomputed set. DETACH so a
# dissolved unit's future goal edge (P19) goes with it.
_PRUNE_UNITS = """
MATCH (u:Unit {tenant_id: $tenant_id})
WHERE NOT u.unit_id IN $keep
DETACH DELETE u
"""

_MERGE_UNIT = """
MERGE (u:Unit {tenant_id: $tenant_id, unit_id: $unit_id})
ON CREATE SET
    u.jurisdiction = $jurisdiction,
    u.created_at = $created_at
"""

# The facet was just deleted above, so MERGE always re-creates it with a fresh
# created_at — correct for derived state. The SAME_WORK edge carries the
# inference: confidence, status (confirmed/candidate), and basis.
_MERGE_FACET_LINK = """
MATCH (u:Unit {tenant_id: $tenant_id, unit_id: $unit_id})
MERGE (f:Facet {tenant_id: $tenant_id, facet_type: $facet_type, facet_id: $facet_id})
ON CREATE SET
    f.jurisdiction = $jurisdiction,
    f.created_at = $created_at
MERGE (f)-[r:SAME_WORK {tenant_id: $tenant_id}]->(u)
ON CREATE SET
    r.jurisdiction = $jurisdiction,
    r.created_at = $created_at
SET
    r.confidence = $confidence,
    r.status = $status,
    r.basis = $basis
"""

_LIST_UNITS = """
MATCH (f:Facet {tenant_id: $tenant_id})
      -[r:SAME_WORK {tenant_id: $tenant_id}]->
      (u:Unit {tenant_id: $tenant_id})
RETURN u.unit_id AS unit_id,
       f.facet_type AS facet_type,
       f.facet_id AS facet_id,
       r.confidence AS confidence,
       r.status AS status,
       r.basis AS basis
ORDER BY u.unit_id ASC, f.facet_type ASC, f.facet_id ASC
"""


# --- Goal-facet templates (D169): the unit→goal SERVES edge -----------------
# The unit's fourth facet (D166): a :Unit serves an :Outcome. Derived state —
# replaced each correlation run. Touches only SERVES (SAME_WORK + LEVER_FOR are
# left intact). An edge whose unit or outcome is absent is silently skipped (the
# MATCH yields no row), so the inference need not pre-check existence.
_DELETE_GOAL_EDGES = """
MATCH (:Unit {tenant_id: $tenant_id})
      -[r:SERVES {tenant_id: $tenant_id}]->
      (:Outcome {tenant_id: $tenant_id})
DELETE r
"""

_MERGE_GOAL_EDGE = """
MATCH (u:Unit {tenant_id: $tenant_id, unit_id: $unit_id})
MATCH (o:Outcome {tenant_id: $tenant_id, outcome_id: $outcome_id})
MERGE (u)-[r:SERVES {tenant_id: $tenant_id}]->(o)
ON CREATE SET
    r.jurisdiction = $jurisdiction,
    r.created_at = $created_at
SET
    r.confidence = $confidence,
    r.status = $status,
    r.basis = $basis
"""

_LIST_GOAL_EDGES = """
MATCH (u:Unit {tenant_id: $tenant_id})
      -[r:SERVES {tenant_id: $tenant_id}]->
      (o:Outcome {tenant_id: $tenant_id})
RETURN u.unit_id AS unit_id,
       o.outcome_id AS outcome_id,
       r.confidence AS confidence,
       r.status AS status,
       r.basis AS basis
ORDER BY u.unit_id ASC, o.outcome_id ASC
"""


# --- Element-evidence templates (D202, S103b): the unit→authored-element edge ---
# The primary evidence write, replacing the goal-level SERVES write (retired). The
# target is an authored element (Lever/Intermediary/External by their id, or the
# Outcome goal node) — the _AUTHORED_ENDPOINT whitelist from 0005. Derived state:
# replaced each correlation run, and the retired SERVES set is deleted alongside.
# S103c (D203): the delete skips user-owned units — a unit the user has corrected
# is never re-derived, so the re-runnable re-match respects correction precedence.
_DELETE_ELEMENT_EVIDENCE = """
MATCH (u:Unit {tenant_id: $tenant_id})-[r:EVIDENCES {tenant_id: $tenant_id}]->()
WHERE coalesce(u.user_owned, false) = false
DELETE r
"""

# S103c (D203): the user-ownership read for the re-match to skip.
_LIST_USER_OWNED_UNITS = """
MATCH (u:Unit {tenant_id: $tenant_id})
WHERE u.user_owned = true
RETURN u.unit_id AS unit_id
"""

# S103i (D209): units belonging to an opportunity — protected from the precision
# filter (a confirmed real opportunity's work is kept untouched).
_LIST_CLUSTERED_UNITS = """
MATCH (u:Unit {tenant_id: $tenant_id})
      -[:BELONGS_TO {tenant_id: $tenant_id}]->(:Opportunity {tenant_id: $tenant_id})
RETURN DISTINCT u.unit_id AS unit_id
"""


def _merge_element_evidence_cypher(tlabel: str, tid: str) -> str:
    return f"""
MATCH (u:Unit {{tenant_id: $tenant_id, unit_id: $unit_id}})
MATCH (e:{tlabel} {{tenant_id: $tenant_id, {tid}: $element_id}})
MERGE (u)-[r:EVIDENCES {{tenant_id: $tenant_id}}]->(e)
ON CREATE SET
    r.jurisdiction = $jurisdiction,
    r.created_at = $created_at
SET
    r.tier = $tier,
    r.status = $status,
    r.basis = $basis
"""


# Every authored element carries outcome_id (the goal), so the goal level derives
# from either endpoint's outcome_id. The element id coalesces the kind's id prop.
# The opportunity scoping (S103h, D208): OPTIONAL MATCH the unit's BELONGS_TO so
# a clustered unit's gate-element binds carry its opportunity, and unclustered
# units read opportunity_id = null (the honest residual).
_LIST_ELEMENT_EVIDENCE = """
MATCH (u:Unit {tenant_id: $tenant_id})
      -[r:EVIDENCES {tenant_id: $tenant_id}]->(e)
WHERE e.outcome_id IS NOT NULL
OPTIONAL MATCH (u)-[:BELONGS_TO {tenant_id: $tenant_id}]->(op:Opportunity)
RETURN u.unit_id AS unit_id,
       labels(e)[0] AS element_kind,
       coalesce(e.lever_id, e.element_id, e.outcome_id) AS element_id,
       e.outcome_id AS outcome_id,
       e.gate_id AS gate_id,
       op.opportunity_id AS opportunity_id,
       r.tier AS tier,
       r.status AS status,
       r.basis AS basis
ORDER BY u.unit_id ASC, element_id ASC
"""


# S103c (D203): single-edge correction mutations + user-ownership. A relink
# retargets one EVIDENCES edge to a different element (both endpoints matched
# before any write, so a bad target leaves the edge intact); an unlink removes
# one edge. Both mark the unit user-owned and the new edge user-corrected — the
# user's binding outranks the matcher's tiers. Multi-attach safe: each touches
# exactly the one (unit, element) edge named, not all of a unit's bindings.
def _unlink_element_evidence_cypher(label: str, id_prop: str) -> str:
    return f"""
MATCH (u:Unit {{tenant_id: $tenant_id, unit_id: $unit_id}})
      -[r:EVIDENCES {{tenant_id: $tenant_id}}]->
      (:{label} {{tenant_id: $tenant_id, {id_prop}: $element_id}})
DELETE r
SET u.user_owned = true
RETURN u.unit_id AS unit_id
"""


def _relink_element_evidence_cypher(
    flabel: str, fid: str, tlabel: str, tid: str
) -> str:
    return f"""
MATCH (u:Unit {{tenant_id: $tenant_id, unit_id: $unit_id}})
      -[r:EVIDENCES {{tenant_id: $tenant_id}}]->
      (:{flabel} {{tenant_id: $tenant_id, {fid}: $from_id}})
MATCH (e:{tlabel} {{tenant_id: $tenant_id, {tid}: $to_id}})
DELETE r
MERGE (u)-[nr:EVIDENCES {{tenant_id: $tenant_id}}]->(e)
ON CREATE SET nr.jurisdiction = $jurisdiction, nr.created_at = $created_at
SET nr.tier = 'user', nr.status = 'confirmed', nr.basis = 'user-corrected',
    u.user_owned = true
RETURN u.unit_id AS unit_id
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
        aliases: Sequence[str] = (),
        domain: str | None = None,
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
            "aliases": list(aliases),
            "domain": domain,
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

    async def archive_outcome(self, *, outcome_id: UUID) -> bool:
        """Mark a goal archived (S103e, D205) — a reversible, non-destructive
        removal (the no-auto-deletion invariant: a user-initiated removal marks,
        never erases). Returns ``True`` when the goal was found, ``False`` when
        absent or cross-tenant."""
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "outcome_id": str(outcome_id),
            "archived_at": _now_utc(),
        }
        result = await session.run(_ARCHIVE_OUTCOME, params)
        return await result.single() is not None

    async def unarchive_outcome(self, *, outcome_id: UUID) -> bool:
        """Re-activate an archived goal (S103e, D205) — removes the archive
        marker so the goal returns whole to every read (its CDD elements, binds
        and audit history were never touched). Returns ``True`` when found."""
        session = self._bound_session
        params = {"tenant_id": self._tenant_id, "outcome_id": str(outcome_id)}
        result = await session.run(_UNARCHIVE_OUTCOME, params)
        return await result.single() is not None

    async def list_archived_outcome_ids(self) -> list[UUID]:
        """Return the ids of every archived goal (S103e, D205) — the complement
        of ``list_outcomes`` (which is active-only). Reactivation reads this to
        restore the whole archived set without depending on seed-module ids."""
        session = self._bound_session
        params = {"tenant_id": self._tenant_id}
        result = await session.run(_LIST_ARCHIVED_OUTCOME_IDS, params)
        rows = await result.data()
        return [UUID(row["outcome_id"]) for row in rows]

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
                    aliases=tuple(row["aliases"] or ()),
                    domain=row["domain"],
                    levers=(lever,),
                )
            else:
                existing = by_outcome[oid]
                by_outcome[oid] = replace(
                    existing, levers=existing.levers + (lever,)
                )
        return [by_outcome[oid] for oid in order]

    # --- Authored CDD layer (S102, D200) -----------------------------------

    async def merge_authored_element(
        self,
        *,
        outcome_id: UUID,
        element_kind: str,
        element_id: UUID,
        label: str,
        provenance_origin: str,
        proof_state: str,
        gate_id: UUID | None = None,
    ) -> None:
        """MERGE an authored CDD element node (S102, D200). The label is composed
        from the whitelist (Neo4j labels are not parameterisable). ``gate_id``
        (S103g, D207) scopes the element to a gate's local CDD; goal-level
        elements pass ``None`` (the property is then absent)."""
        node_label, id_prop = _authored_node(element_kind)
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "jurisdiction": self._jurisdiction,
            "outcome_id": str(outcome_id),
            "gate_id": str(gate_id) if gate_id is not None else None,
            "element_id": str(element_id),
            "label": label,
            "provenance_origin": provenance_origin,
            "proof_state": proof_state,
            "created_at": _now_utc(),
        }
        await session.run(
            _merge_authored_element_cypher(node_label, id_prop), params
        )

    # --- Process gates (S103g, D207) ---------------------------------------

    async def merge_gate(
        self,
        *,
        gate_id: UUID,
        outcome_id: UUID,
        name: str,
        gate_order: int,
        local_outcome: str,
        local_goal: str,
        provenance_origin: str,
        proof_state: str,
        step_commitment_id: UUID | None = None,
    ) -> None:
        """MERGE a process-flow gate (D207). The gate node is its CDD's
        local-outcome endpoint; it references a D163 step where one exists."""
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "jurisdiction": self._jurisdiction,
            "gate_id": str(gate_id),
            "outcome_id": str(outcome_id),
            "name": name,
            "gate_order": gate_order,
            "local_outcome": local_outcome,
            "local_goal": local_goal,
            "provenance_origin": provenance_origin,
            "proof_state": proof_state,
            "step_commitment_id": (
                str(step_commitment_id) if step_commitment_id is not None else None
            ),
            "created_at": _now_utc(),
        }
        await session.run(_MERGE_GATE, params)

    async def list_gates(self, *, outcome_id: UUID) -> list[dict]:
        """Return a goal's gates, ordered by gate_order (D207)."""
        session = self._bound_session
        params = {"tenant_id": self._tenant_id, "outcome_id": str(outcome_id)}
        result = await session.run(_LIST_GATES, params)
        return list(await result.data())

    # --- Process instances / opportunities (S103h, D208) -------------------

    async def merge_opportunity(
        self,
        *,
        opportunity_id: UUID,
        outcome_id: UUID,
        name: str,
        current_gate_id: UUID | None,
        provenance_origin: str,
        proof_state: str,
        source: str | None = None,
    ) -> None:
        """MERGE an opportunity Flow item (D208)."""
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "jurisdiction": self._jurisdiction,
            "opportunity_id": str(opportunity_id),
            "outcome_id": str(outcome_id),
            "name": name,
            "current_gate_id": (
                str(current_gate_id) if current_gate_id is not None else None
            ),
            "provenance_origin": provenance_origin,
            "proof_state": proof_state,
            "source": source,
            "created_at": _now_utc(),
        }
        await session.run(_MERGE_OPPORTUNITY, params)

    async def list_opportunities(self, *, outcome_id: UUID) -> list[dict]:
        """Return a goal's opportunities with their unit counts (D208)."""
        session = self._bound_session
        params = {"tenant_id": self._tenant_id, "outcome_id": str(outcome_id)}
        result = await session.run(_LIST_OPPORTUNITIES, params)
        return list(await result.data())

    async def attach_unit_to_opportunity(
        self, *, unit_id: UUID, opportunity_id: UUID
    ) -> None:
        """MERGE the BELONGS_TO membership edge (D208) — idempotent."""
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "jurisdiction": self._jurisdiction,
            "unit_id": str(unit_id),
            "opportunity_id": str(opportunity_id),
            "created_at": _now_utc(),
        }
        await session.run(_ATTACH_UNIT_TO_OPPORTUNITY, params)

    async def clear_opportunity_units(self, *, opportunity_id: UUID) -> None:
        """Delete an opportunity's BELONGS_TO edges so a re-instantiation
        reconciles cleanly (D208)."""
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "opportunity_id": str(opportunity_id),
        }
        await session.run(_CLEAR_OPPORTUNITY_UNITS, params)

    async def set_element_gate(
        self, *, element_kind: str, element_id: UUID, gate_id: UUID
    ) -> bool:
        """Relocate an authored element into a gate (D207): set its gate_id,
        preserving the node + label + provenance. Returns True when matched."""
        node_label, id_prop = _authored_node(element_kind)
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "element_id": str(element_id),
            "gate_id": str(gate_id),
        }
        result = await session.run(
            _set_element_gate_cypher(node_label, id_prop), params
        )
        return await result.single() is not None

    async def delete_authored_edge(
        self,
        *,
        edge_type: str,
        source_kind: str,
        source_id: UUID,
        target_kind: str,
        target_id: UUID,
    ) -> None:
        """Delete one authored edge by its endpoints (D207 — edge migration)."""
        if edge_type not in _AUTHORED_EDGE_TYPES:
            raise ValueError(f"unknown authored edge type: {edge_type!r}")
        slabel, sid = _authored_endpoint(source_kind)
        tlabel, tid = _authored_endpoint(target_kind)
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "source_id": str(source_id),
            "target_id": str(target_id),
        }
        await session.run(
            _delete_authored_edge_cypher(edge_type, slabel, sid, tlabel, tid),
            params,
        )

    async def merge_authored_edge(
        self,
        *,
        edge_type: str,
        source_kind: str,
        source_id: UUID,
        target_kind: str,
        target_id: UUID,
    ) -> None:
        """MERGE an authored causal edge (FEEDS / INFLUENCES, S102, D200)."""
        if edge_type not in _AUTHORED_EDGE_TYPES:
            raise ValueError(f"unknown authored edge type: {edge_type!r}")
        slabel, sid = _authored_endpoint(source_kind)
        tlabel, tid = _authored_endpoint(target_kind)
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "jurisdiction": self._jurisdiction,
            "source_id": str(source_id),
            "target_id": str(target_id),
            "created_at": _now_utc(),
        }
        await session.run(
            _merge_authored_edge_cypher(edge_type, slabel, sid, tlabel, tid),
            params,
        )

    async def read_authored_cdd(self, *, outcome_id: UUID) -> AuthoredCddRecord:
        """Read a goal's authored elements + edges for proof review (S102)."""
        session = self._bound_session
        params = {"tenant_id": self._tenant_id, "outcome_id": str(outcome_id)}
        elements: list[AuthoredElementRecord] = []
        for kind, cypher in (
            ("lever", _LIST_AUTHORED_LEVERS),
            ("intermediary", _LIST_AUTHORED_INTERMEDIARIES),
            ("external", _LIST_AUTHORED_EXTERNALS),
        ):
            result = await session.run(cypher, params)
            for row in await result.data():
                gate_id = row.get("gate_id")
                elements.append(
                    AuthoredElementRecord(
                        element_kind=kind,
                        element_id=UUID(row["element_id"]),
                        outcome_id=outcome_id,
                        label=row["label"],
                        provenance_origin=row["provenance_origin"],
                        proof_state=row["proof_state"],
                        gate_id=UUID(gate_id) if gate_id else None,
                    )
                )
        edge_result = await session.run(_LIST_AUTHORED_EDGES, params)
        edges = tuple(
            AuthoredEdgeRecord(
                edge_type=row["edge_type"],
                source_kind=str(row["source_kind"]).lower(),
                source_id=UUID(row["source_id"]),
                target_kind=str(row["target_kind"]).lower(),
                target_id=UUID(row["target_id"]),
                needs_review=bool(row["needs_review"]),
            )
            for row in await edge_result.data()
        )
        outcome_result = await session.run(_READ_AUTHORED_OUTCOME, params)
        outcome_row = await outcome_result.single()
        expected_outcome = (
            outcome_row["expected_outcome"] if outcome_row is not None else None
        )
        # Coalesce the proof signal for the S102 drafts that predate it: an
        # authored outcome with no recorded origin/proof was LLM-drafted/pending.
        if expected_outcome is not None:
            outcome_origin = outcome_row["provenance_origin"] or "llm_drafted"
            outcome_proof = outcome_row["proof_state"] or "pending"
        else:
            outcome_origin = None
            outcome_proof = None
        return AuthoredCddRecord(
            outcome_id=outcome_id,
            elements=tuple(elements),
            edges=edges,
            expected_outcome=expected_outcome,
            expected_outcome_origin=outcome_origin,
            expected_outcome_proof_state=outcome_proof,
            disposition_moat=(
                outcome_row["disposition_moat"] if outcome_row else None
            ),
            disposition_pipeline=(
                outcome_row["disposition_pipeline"] if outcome_row else None
            ),
            disposition_market=(
                outcome_row["disposition_market"] if outcome_row else None
            ),
            disposition_parked=(
                outcome_row["disposition_parked"] if outcome_row else None
            ),
        )

    async def set_outcome_disposition(
        self, *, outcome_id: UUID, moat: int, pipeline: int, market: int,
        parked: int,
    ) -> None:
        """Persist the precision pass's disposition counts on the goal (D210)."""
        session = self._bound_session
        await session.run(_SET_OUTCOME_DISPOSITION, {
            "tenant_id": self._tenant_id, "outcome_id": str(outcome_id),
            "moat": moat, "pipeline": pipeline, "market": market,
            "parked": parked,
        })

    async def set_authored_outcome(
        self,
        *,
        outcome_id: UUID,
        expected_outcome: str,
        provenance_origin: str,
        proof_state: str,
    ) -> None:
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "outcome_id": str(outcome_id),
            "expected_outcome": expected_outcome,
            "provenance_origin": provenance_origin,
            "proof_state": proof_state,
        }
        await session.run(_SET_AUTHORED_OUTCOME, params)

    async def accept_authored_outcome(self, *, outcome_id: UUID) -> bool:
        session = self._bound_session
        params = {"tenant_id": self._tenant_id, "outcome_id": str(outcome_id)}
        result = await session.run(_ACCEPT_AUTHORED_OUTCOME, params)
        return await result.single() is not None

    async def clear_authored_outcome(self, *, outcome_id: UUID) -> bool:
        session = self._bound_session
        params = {"tenant_id": self._tenant_id, "outcome_id": str(outcome_id)}
        result = await session.run(_CLEAR_AUTHORED_OUTCOME, params)
        return await result.single() is not None

    async def set_authored_proof_state(
        self, *, element_kind: str, element_id: UUID, proof_state: str
    ) -> bool:
        node_label, id_prop = _authored_node(element_kind)
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "element_id": str(element_id),
            "proof_state": proof_state,
        }
        result = await session.run(
            _set_authored_proof_state_cypher(node_label, id_prop), params
        )
        return await result.single() is not None

    async def set_authored_label(
        self, *, element_kind: str, element_id: UUID, label: str
    ) -> bool:
        node_label, id_prop = _authored_node(element_kind)
        session = self._bound_session
        params = {
            "tenant_id": self._tenant_id,
            "element_id": str(element_id),
            "label": label,
        }
        result = await session.run(
            _set_authored_label_cypher(node_label, id_prop), params
        )
        return await result.single() is not None

    async def delete_authored_element(
        self, *, element_kind: str, element_id: UUID
    ) -> bool:
        node_label, id_prop = _authored_node(element_kind)
        session = self._bound_session
        params = {"tenant_id": self._tenant_id, "element_id": str(element_id)}
        result = await session.run(
            _delete_authored_element_cypher(node_label, id_prop), params
        )
        summary = await result.consume()
        return summary.counters.nodes_deleted > 0

    async def reclassify_authored_element(
        self, *, from_kind: str, to_kind: str, element_id: UUID
    ) -> bool:
        """Reclassify an authored element across types (D201, S103a): swap the
        type-label preserving the node + stable id, flip the origin to
        user_authored, and flag (never drop) any now-ungrammatical incident edge.
        Returns ``False`` when the element is absent or cross-tenant."""
        from_label, from_idprop = _authored_node(from_kind)
        to_label, to_idprop = _authored_node(to_kind)
        drop_commitment = from_kind == "lever" and to_kind != "lever"
        session = self._bound_session
        params = {"tenant_id": self._tenant_id, "element_id": str(element_id)}
        result = await session.run(
            _reclassify_authored_element_cypher(
                from_label, from_idprop, to_label, to_idprop,
                drop_commitment=drop_commitment,
            ),
            params,
        )
        if await result.single() is None:
            return False
        await session.run(
            _flag_reclassified_edges_cypher(to_label, to_idprop),
            {**params, "required_type": _required_edge_type(to_kind)},
        )
        return True

    async def replace_units(self, units: Sequence[UnitWrite]) -> None:
        """Replace the bound tenant's work-unit subgraph (D168, D166).

        Derived state (D155): delete the tenant's :Facet nodes + SAME_WORK edges,
        prune :Unit nodes no longer in ``units``, then MERGE each unit + its
        facets + edges. The statements run on one bound session (auto-commit per
        statement — the migration-runner shape; atomicity across statements is
        not required for derived state at dogfooding scale).
        """
        session = self._bound_session
        now = _now_utc()
        await session.run(_DELETE_FACETS, {"tenant_id": self._tenant_id})
        await session.run(
            _PRUNE_UNITS,
            {
                "tenant_id": self._tenant_id,
                "keep": [str(u.unit_id) for u in units],
            },
        )
        for unit in units:
            await session.run(
                _MERGE_UNIT,
                {
                    "tenant_id": self._tenant_id,
                    "jurisdiction": self._jurisdiction,
                    "unit_id": str(unit.unit_id),
                    "created_at": now,
                },
            )
            for link in unit.links:
                await session.run(
                    _MERGE_FACET_LINK,
                    {
                        "tenant_id": self._tenant_id,
                        "jurisdiction": self._jurisdiction,
                        "unit_id": str(unit.unit_id),
                        "facet_type": link.facet_type,
                        "facet_id": str(link.facet_id),
                        "confidence": link.confidence,
                        "status": link.status,
                        "basis": link.basis,
                        "created_at": now,
                    },
                )

    async def list_units(self) -> Sequence[UnitGraphRecord]:
        """Return every unit with its facet edges for the bound tenant (D168).

        One Cypher row per (unit, facet); aggregated here into one
        ``UnitGraphRecord`` per unit — the wrapper owns the Cypher boundary, so
        the aggregation stays on this side of the fence (the ``list_outcomes``
        shape).
        """
        session = self._bound_session
        params = {"tenant_id": self._tenant_id}
        result = await session.run(_LIST_UNITS, params)
        rows = await result.data()
        by_unit: dict[str, UnitGraphRecord] = {}
        order: list[str] = []
        for row in rows:
            uid = row["unit_id"]
            link = FacetLinkRecord(
                facet_type=row["facet_type"],
                facet_id=UUID(row["facet_id"]),
                confidence=row["confidence"],
                status=row["status"],
                basis=row["basis"],
            )
            if uid not in by_unit:
                order.append(uid)
                by_unit[uid] = UnitGraphRecord(
                    unit_id=UUID(uid), links=(link,)
                )
            else:
                existing = by_unit[uid]
                by_unit[uid] = replace(
                    existing, links=existing.links + (link,)
                )
        return [by_unit[uid] for uid in order]

    async def replace_goal_edges(self, edges: Sequence[GoalEdgeWrite]) -> None:
        """Replace the bound tenant's unit→goal SERVES edges (D169).

        Deletes the tenant's SERVES edges, then MERGEs the new set. Touches only
        SERVES (SAME_WORK + LEVER_FOR untouched). An edge whose unit or outcome
        is absent is silently skipped (the MATCH yields no row). Auto-commit per
        statement — the derived-state shape (the migration-runner pattern).
        """
        session = self._bound_session
        now = _now_utc()
        await session.run(_DELETE_GOAL_EDGES, {"tenant_id": self._tenant_id})
        for edge in edges:
            await session.run(
                _MERGE_GOAL_EDGE,
                {
                    "tenant_id": self._tenant_id,
                    "jurisdiction": self._jurisdiction,
                    "unit_id": str(edge.unit_id),
                    "outcome_id": str(edge.outcome_id),
                    "confidence": edge.confidence,
                    "status": edge.status,
                    "basis": edge.basis,
                    "created_at": now,
                },
            )

    async def list_goal_edges(self) -> Sequence[GoalEdgeRecord]:
        """Return every unit→goal SERVES edge for the bound tenant (D169)."""
        session = self._bound_session
        params = {"tenant_id": self._tenant_id}
        result = await session.run(_LIST_GOAL_EDGES, params)
        rows = await result.data()
        return [
            GoalEdgeRecord(
                unit_id=UUID(row["unit_id"]),
                outcome_id=UUID(row["outcome_id"]),
                confidence=row["confidence"],
                status=row["status"],
                basis=row["basis"],
            )
            for row in rows
        ]

    async def replace_element_evidence(
        self, evidence: Sequence[ElementEvidenceWrite]
    ) -> None:
        """Replace the tenant's unit→element EVIDENCES edges (D202, S103b).

        Deletes the tenant's EVIDENCES edges and the retired SERVES edges, then
        MERGEs the new evidence set. The element endpoint label/id-property is
        composed from the authored whitelist (an unknown kind raises). An edge
        whose unit or element is absent is silently skipped.
        """
        session = self._bound_session
        now = _now_utc()
        await session.run(
            _DELETE_ELEMENT_EVIDENCE, {"tenant_id": self._tenant_id}
        )
        await session.run(_DELETE_GOAL_EDGES, {"tenant_id": self._tenant_id})
        for ev in evidence:
            tlabel, tid = _authored_endpoint(ev.element_kind)
            await session.run(
                _merge_element_evidence_cypher(tlabel, tid),
                {
                    "tenant_id": self._tenant_id,
                    "jurisdiction": self._jurisdiction,
                    "unit_id": str(ev.unit_id),
                    "element_id": str(ev.element_id),
                    "tier": ev.tier,
                    "status": ev.status,
                    "basis": ev.basis,
                    "created_at": now,
                },
            )

    async def list_element_evidence(
        self,
    ) -> Sequence[ElementEvidenceRecord]:
        """Return every unit→element EVIDENCES edge for the bound tenant (D202)."""
        session = self._bound_session
        result = await session.run(
            _LIST_ELEMENT_EVIDENCE, {"tenant_id": self._tenant_id}
        )
        rows = await result.data()
        out = []
        for row in rows:
            gate_id = row.get("gate_id")
            opportunity_id = row.get("opportunity_id")
            out.append(
                ElementEvidenceRecord(
                    unit_id=UUID(row["unit_id"]),
                    element_kind=str(row["element_kind"]).lower(),
                    element_id=UUID(row["element_id"]),
                    outcome_id=UUID(row["outcome_id"]),
                    tier=row["tier"],
                    status=row["status"],
                    basis=row["basis"],
                    gate_id=UUID(gate_id) if gate_id else None,
                    opportunity_id=UUID(opportunity_id) if opportunity_id else None,
                )
            )
        return out

    async def list_user_owned_unit_ids(self) -> set[UUID]:
        """Unit ids the user has corrected (user_owned), for the re-match to skip
        (D203, S103c)."""
        session = self._bound_session
        result = await session.run(
            _LIST_USER_OWNED_UNITS, {"tenant_id": self._tenant_id}
        )
        return {UUID(row["unit_id"]) for row in await result.data()}

    async def list_clustered_unit_ids(self) -> set[UUID]:
        """Unit ids belonging to an opportunity (D209) — protected from the
        precision filter so a confirmed real opportunity's work is kept."""
        session = self._bound_session
        result = await session.run(
            _LIST_CLUSTERED_UNITS, {"tenant_id": self._tenant_id}
        )
        return {UUID(row["unit_id"]) for row in await result.data()}

    async def unlink_element_evidence(
        self, *, unit_id: UUID, element_kind: str, element_id: UUID
    ) -> bool:
        """Remove one unit→element EVIDENCES edge and mark the unit user-owned
        (D203). Returns ``False`` when the edge is absent or cross-tenant."""
        label, id_prop = _authored_endpoint(element_kind)
        session = self._bound_session
        result = await session.run(
            _unlink_element_evidence_cypher(label, id_prop),
            {
                "tenant_id": self._tenant_id,
                "unit_id": str(unit_id),
                "element_id": str(element_id),
            },
        )
        return await result.single() is not None

    async def relink_element_evidence(
        self,
        *,
        unit_id: UUID,
        from_kind: str,
        from_element_id: UUID,
        to_kind: str,
        to_element_id: UUID,
    ) -> bool:
        """Retarget one unit→element EVIDENCES edge to a different element, mark it
        user-corrected and the unit user-owned (D203). Both endpoints are matched
        before any write, so a missing from-edge or to-element is a no-op (returns
        ``False``)."""
        flabel, fid = _authored_endpoint(from_kind)
        tlabel, tid = _authored_endpoint(to_kind)
        session = self._bound_session
        result = await session.run(
            _relink_element_evidence_cypher(flabel, fid, tlabel, tid),
            {
                "tenant_id": self._tenant_id,
                "jurisdiction": self._jurisdiction,
                "unit_id": str(unit_id),
                "from_id": str(from_element_id),
                "to_id": str(to_element_id),
                "created_at": _now_utc(),
            },
        )
        return await result.single() is not None


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
