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
class OutcomeGraphRecord:
    """One Outcome joined to its lever edge as read from the graph.

    ``ladder`` is the ordered tuple of named levels for a progressive goal
    (empty for non-progressive modes); ``current_target_level`` is the level
    the goal is currently aiming at (``None`` for non-progressive modes).
    """

    outcome_id: UUID
    name: str
    control: str
    subject: str
    commitment_id: UUID
    mode: str
    ladder: tuple[str, ...]
    current_target_level: str | None


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
    ) -> None:
        """Idempotently MERGE an ``:Outcome`` node by ``(tenant_id, outcome_id)``.

        Re-running updates ``name``/``control``/``subject`` and leaves
        ``created_at`` from the first MERGE intact.
        """
        ...

    async def merge_lever_for_outcome(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        commitment_id: UUID,
        mode: str,
        ladder: Sequence[str],
        current_target_level: str | None,
    ) -> None:
        """MERGE the ``:Lever`` node (by ``(tenant_id, commitment_id)``) and the
        ``LEVER_FOR`` edge to the Outcome, setting the edge's ``mode``,
        ``ladder``, and ``current_target_level``. The Outcome must already
        exist (caller merges it first); the lever is a thin reference to the
        Postgres commitment, not a copy of it.
        """
        ...

    async def set_lever_target(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        commitment_id: UUID,
        current_target_level: str,
    ) -> str | None:
        """Set the ``current_target_level`` on an existing ``LEVER_FOR`` edge
        (the explicit raise action — never automatic, D9). Returns the new
        level on success, ``None`` when the edge is absent or cross-tenant.
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


__all__ = ["OutcomeGraphPort", "OutcomeGraphRecord"]
