"""UnitGraphPort — the daily-driver consumer port for the work-unit graph (D168).

The same-work correlation is a Padhanam-native graph layer (D166): a ``:Unit``
anchor node, thin ``:Facet`` reference nodes, and the ``SAME_WORK`` edge. The
graph lives behind ingestion's ``TenantScopedNeo4jSession`` wrapper (the only
Cypher home — the AST/``neo4j-confined`` fence), which the daily-driver context
cannot reach directly (it may import neither ``neo4j`` nor the ingestion
context). So daily_driver declares this consumer port and the apps composition
root bridges it to ingestion's ``UnitGraphPort`` (the ``GoalGraphPort``
precedent).

The write speaks the daily-driver ``WorkUnit`` domain (the bridge maps it onto
the generic graph capability); the read returns thin ``UnitRecord`` rows — the
graph holds only facet *references*, so the units reader enriches them with
titles from the caches at display time. Ports layer is pure per D16 — no
SQLAlchemy, no neo4j.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from contexts.daily_driver.domain.goal_assessment import GoalEdge
from contexts.daily_driver.domain.work_unit import (
    UnitFacetRef,
    UnitRecord,
    WorkUnit,
)
from shared_kernel import TenantContext


class UnitGraphPort(Protocol):
    """Read/replace port for the work-unit correlation graph (D168)."""

    async def replace_units(
        self, *, tenant_context: TenantContext, units: Sequence[WorkUnit]
    ) -> None:
        """Replace the tenant's whole unit subgraph with ``units`` (D168).

        Correlation is derived state (D155): each run replaces the prior
        ``:Unit`` / ``:Facet`` / ``SAME_WORK`` set so stale links and orphaned
        units do not accumulate. The graph stores only ids and edge properties —
        never the facet's (decrypted) title. Idempotent: the same caches yield
        the same units (deterministic unit ids).
        """
        ...

    async def list_units(
        self, *, tenant_context: TenantContext
    ) -> tuple[UnitRecord, ...]:
        """Return the tenant's correlated units as thin records, ordered by id.

        Cross-tenant rows never surface (the wrapper binds ``tenant_id`` into
        every predicate).
        """
        ...

    async def replace_goal_edges(
        self, *, tenant_context: TenantContext, edges: Sequence[GoalEdge]
    ) -> None:
        """Replace the tenant's unit→goal ``SERVES`` edges (D169).

        Derived state, recomputed each correlation run; touches only the goal
        facet (the unit ``SAME_WORK`` subgraph and the goal ``LEVER_FOR`` edges
        are left intact). Stores only ids + the inference's edge properties.
        """
        ...

    async def list_goal_edges(
        self, *, tenant_context: TenantContext
    ) -> tuple[GoalEdge, ...]:
        """Return the tenant's unit→goal ``SERVES`` edges (D169)."""
        ...


__all__ = ["UnitFacetRef", "UnitGraphPort", "UnitRecord"]
