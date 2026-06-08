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

from dataclasses import dataclass
from typing import Protocol, Sequence
from uuid import UUID

from contexts.daily_driver.domain.work_unit import (
    FacetType,
    LinkStatus,
    WorkUnit,
)
from shared_kernel import TenantContext


@dataclass(frozen=True)
class UnitFacetRef:
    """One facet's membership as read back from the graph (thin — id only)."""

    facet_type: FacetType
    facet_id: UUID
    confidence: float
    status: LinkStatus
    basis: str


@dataclass(frozen=True)
class UnitRecord:
    """One correlated unit as read back from the graph (D168).

    ``facets`` carries the thin references (no title — the graph stores only the
    cache row's id); the units reader joins each back to its cache for display.
    """

    unit_id: UUID
    facets: tuple[UnitFacetRef, ...]


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


__all__ = ["UnitFacetRef", "UnitRecord", "UnitGraphPort"]
