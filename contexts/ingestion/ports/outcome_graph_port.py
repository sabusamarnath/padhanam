"""OutcomeGraphPort — the typed goal-graph surface on the shared graph (D163).

The whole-life goal taxonomy (D163) models a goal as an ``:Outcome`` node and
its lever as a ``:Lever`` node connected by a ``LEVER_FOR`` edge that carries
the goal's ``mode`` and, for a progressive goal, an ordered level ladder plus a
current target level. This port is the typed graph capability for that shape.

It is a *sibling* of ``GraphRepositoryPort``: the existing ``:Entity`` /
``Relationship`` vocabulary is built for LLM-extracted source entities keyed by
``source_chunk_ids`` and cannot carry a mode or a target ladder, so the
Outcome/lever shape is a new node-and-edge family rather than a reuse. It lives
behind the same ``TenantScopedNeo4jSession`` wrapper (the single Cypher surface
fenced by the ``neo4j-confined`` contract and the AST enforcement test), so no
raw driver call enters domain code.

The port is deliberately goal-agnostic at the graph boundary: it speaks of
Outcomes and Levers in primitive terms (ids, names, the mode string, the ladder
strings). The daily-driver context owns the *goal* concept and consumes this
through its own ``GoalGraphPort`` + an apps-composition-root bridge (the
calendar/email ``MeetingGraphIndexPort`` precedent). The ``:Lever`` node is a
thin *reference* to the commitment that lives in Postgres — it carries only the
``commitment_id``, never a copy of the commitment's row (D163 Step 0 F3).

Every node and edge carries ``tenant_id`` + ``jurisdiction`` and is reached only
through the tenant-scoped wrapper, so property-based isolation per D63/D64
holds for the goal graph exactly as it does for the entity graph.

Errors reuse ``GraphRepositoryError`` / ``GraphRepositoryConfigurationError``
from ``graph_repository_port`` so callers handle one error taxonomy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence
from uuid import UUID

from shared_kernel import TenantContext


@dataclass(frozen=True)
class LeverEdgeRecord:
    """One ``LEVER_FOR`` edge as read from the graph (D163, S63).

    ``commitment_id`` is the thin :Lever reference's Postgres commitment id;
    ``step_order`` + ``step_state`` are the lever's relationship-level
    attributes for a sequence goal (``None`` for a single-lever progressive
    goal).
    """

    commitment_id: UUID
    step_order: int | None = None
    step_state: str | None = None


@dataclass(frozen=True)
class OutcomeGraphRecord:
    """One Outcome with all its lever edges as read from the graph (D163).

    Goal-level properties live on the Outcome (the D163 clarification):
    ``ladder`` + ``current_target_level`` for a progressive goal,
    ``terminal_target`` + ``terminal_state`` for a sequence goal (each ``None``/
    empty for the other shape). ``levers`` carries every ``LEVER_FOR`` edge — one
    for a progressive goal, the ordered chain for a sequence goal.
    """

    outcome_id: UUID
    name: str
    control: str
    subject: str
    mode: str
    ladder: tuple[str, ...]
    current_target_level: str | None
    terminal_target: str | None = None
    terminal_state: str | None = None
    levers: tuple[LeverEdgeRecord, ...] = ()
    # Goal-owned alias terms (category synonyms, D174 tier two).
    aliases: tuple[str, ...] = ()
    # Goal domain (D179): the surface tier this goal's covered work renders
    # under (work / personal / family). None when unset (the read falls through
    # to the connection default).
    domain: str | None = None


@dataclass(frozen=True)
class AuthoredElementRecord:
    """One authored CDD element as read from the graph (S102, D200).

    ``element_kind`` is ``lever`` / ``intermediary`` / ``external`` (the node
    label, lower-cased). ``element_id`` is the element's stable id (an authored
    lever's ``lever_id``; an intermediary's / external's ``element_id``).
    ``outcome_id`` is the goal whose CDD this element belongs to. ``label`` is
    the human-readable text; ``provenance_origin`` and ``proof_state`` carry the
    D200 authored signal.
    """

    element_kind: str
    element_id: UUID
    outcome_id: UUID
    label: str
    provenance_origin: str
    proof_state: str


@dataclass(frozen=True)
class AuthoredEdgeRecord:
    """One authored causal edge as read from the graph (S102, D200).

    ``edge_type`` is ``FEEDS`` or ``INFLUENCES``; ``source_kind`` / ``target_kind``
    are the endpoint labels lower-cased (``lever`` / ``intermediary`` /
    ``external`` / ``outcome``); the ids are the endpoints' stable ids.
    """

    edge_type: str
    source_kind: str
    source_id: UUID
    target_kind: str
    target_id: UUID


@dataclass(frozen=True)
class AuthoredCddRecord:
    """A goal's authored CDD as read from the graph (S102, D200)."""

    outcome_id: UUID
    elements: tuple[AuthoredElementRecord, ...]
    edges: tuple[AuthoredEdgeRecord, ...]


class OutcomeGraphPort(Protocol):
    """Typed goal-graph capability on the shared Neo4j instance (D163)."""

    async def merge_outcome(
        self,
        *,
        tenant_context: TenantContext,
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
        """Idempotently MERGE an ``:Outcome`` node by ``(tenant_id, outcome_id)``.

        Per the D163 clarification (S63), the goal-level properties live on the
        node: ``mode``, the ``ladder`` + ``current_target_level`` (progressive),
        and ``terminal_target`` + ``terminal_state`` (sequence). Re-running
        updates them and leaves ``created_at`` from the first MERGE intact.
        """
        ...

    async def merge_lever_for_outcome(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        commitment_id: UUID,
        step_order: int | None = None,
        step_state: str | None = None,
    ) -> None:
        """MERGE the ``:Lever`` node (by ``(tenant_id, commitment_id)``) and the
        ``LEVER_FOR`` edge to the Outcome. The edge carries only that the lever
        serves the outcome plus, for a sequence goal, the lever's
        relationship-level ``step_order`` + ``step_state`` (the D163
        clarification). The Outcome must already exist (caller merges it first);
        the lever is a thin reference to the Postgres commitment, not a copy.
        """
        ...

    async def set_outcome_target(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        current_target_level: str,
    ) -> str | None:
        """Set the ``current_target_level`` on an existing ``:Outcome`` node
        (the explicit raise action — never automatic, D9). The target is a
        goal-level property (D163 clarification), so the raise needs no lever
        id. Returns the new level on success, ``None`` when the outcome is
        absent or cross-tenant.
        """
        ...

    async def list_outcomes(
        self,
        *,
        tenant_context: TenantContext,
    ) -> Sequence[OutcomeGraphRecord]:
        """Return every Outcome with its lever edge for the bound tenant,
        ordered by name. Cross-tenant rows never surface (the wrapper binds
        ``tenant_id`` into every predicate)."""
        ...


    # --- Authored CDD layer (S102, D200) -----------------------------------

    async def merge_authored_element(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        element_kind: str,
        element_id: UUID,
        label: str,
        provenance_origin: str,
        proof_state: str,
    ) -> None:
        """Idempotently MERGE an authored CDD element (S102, D200).

        ``element_kind`` is ``lever`` / ``intermediary`` / ``external`` — the
        node label, drawn from a whitelist (Neo4j labels are not parameterisable,
        so the wrapper composes the literal label from the whitelist, never from
        free input). An authored lever identifies by ``lever_id`` and may have no
        ``commitment_id`` yet; an intermediary/external identifies by
        ``element_id``. ``provenance_origin`` and ``proof_state`` carry the D200
        authored signal.
        """
        ...

    async def merge_authored_edge(
        self,
        *,
        tenant_context: TenantContext,
        edge_type: str,
        source_kind: str,
        source_id: UUID,
        target_kind: str,
        target_id: UUID,
    ) -> None:
        """Idempotently MERGE an authored causal edge (``FEEDS`` / ``INFLUENCES``,
        S102, D200) between two authored elements (or to the ``:Outcome``). Kinds
        and edge type are whitelisted; endpoints must already exist."""
        ...

    async def read_authored_cdd(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
    ) -> AuthoredCddRecord:
        """Read a goal's authored CDD — its elements (with origin + proof state)
        and authored edges — for proof review (S102, D200)."""
        ...

    async def set_authored_proof_state(
        self,
        *,
        tenant_context: TenantContext,
        element_kind: str,
        element_id: UUID,
        proof_state: str,
    ) -> bool:
        """Set an authored element's ``proof_state`` (the accept path, S102).
        Returns ``True`` when an element was updated, ``False`` when absent or
        cross-tenant."""
        ...

    async def set_authored_label(
        self,
        *,
        tenant_context: TenantContext,
        element_kind: str,
        element_id: UUID,
        label: str,
    ) -> bool:
        """Edit an authored element's ``label`` and flip its
        ``provenance_origin`` to ``user_authored`` (the correct path, S102/D200).
        Returns ``True`` when updated, ``False`` when absent or cross-tenant."""
        ...

    async def delete_authored_element(
        self,
        *,
        tenant_context: TenantContext,
        element_kind: str,
        element_id: UUID,
    ) -> bool:
        """Remove an authored element and its authored edges (the reject path,
        S102) — a user-initiated delete (allowed; the no-auto-deletion invariant
        forbids *auto* deletion, not user-asked removal). Returns ``True`` when an
        element was removed."""
        ...


__all__ = [
    "AuthoredCddRecord",
    "AuthoredEdgeRecord",
    "AuthoredElementRecord",
    "LeverEdgeRecord",
    "OutcomeGraphPort",
    "OutcomeGraphRecord",
]
