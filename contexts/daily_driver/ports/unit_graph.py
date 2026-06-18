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
from uuid import UUID

from contexts.daily_driver.domain.cdd import ElementKind
from contexts.daily_driver.domain.goal_assessment import (
    ElementEvidence,
    GoalEdge,
)
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

    async def replace_element_evidence(
        self, *, tenant_context: TenantContext, evidence: Sequence[ElementEvidence]
    ) -> None:
        """Replace the tenant's unit→authored-element ``EVIDENCES`` edges (D202).

        The primary matcher write (S103b), replacing the retired goal-level
        ``SERVES`` write: derived state, recomputed each correlation run, and the
        old ``SERVES`` set is deleted alongside. Multi-attach is natural — a unit
        carries one edge per element it evidences.
        """
        ...

    async def list_element_evidence(
        self, *, tenant_context: TenantContext
    ) -> tuple[ElementEvidence, ...]:
        """Return the tenant's unit→element ``EVIDENCES`` edges (D202, S103b)."""
        ...

    async def list_goal_edges(
        self, *, tenant_context: TenantContext
    ) -> tuple[GoalEdge, ...]:
        """Return the tenant's unit→goal edges — **derived on read** from element
        evidence (D202, S103b), no longer the written ``SERVES`` edge. The shape
        is unchanged so the coverage/grouping readers are untouched."""
        ...

    async def list_user_owned_unit_ids(
        self, *, tenant_context: TenantContext
    ) -> set[UUID]:
        """Return the unit ids the user has corrected (D203, S103c) — the re-match
        skips these so a correction is never overwritten."""
        ...

    async def unlink_element_evidence(
        self,
        *,
        tenant_context: TenantContext,
        unit_id: UUID,
        element_kind: ElementKind,
        element_id: UUID,
    ) -> bool:
        """Remove one unit→element binding and mark the unit user-owned (D203).
        Returns ``False`` when the binding is absent or cross-tenant."""
        ...

    async def relink_element_evidence(
        self,
        *,
        tenant_context: TenantContext,
        unit_id: UUID,
        from_kind: ElementKind,
        from_element_id: UUID,
        to_kind: ElementKind,
        to_element_id: UUID,
    ) -> bool:
        """Retarget one unit→element binding to a different element, mark it
        user-corrected and the unit user-owned (D203). Returns ``False`` when the
        from-binding or the to-element is absent."""
        ...


__all__ = ["UnitFacetRef", "UnitGraphPort", "UnitRecord"]
