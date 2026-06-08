"""UnitGraphPort — the typed work-unit graph surface on the shared graph (D168).

The plan-side work-unit model (D166): a *unit of work* is one thing seen from up
to four facets. P18 records the correlation of the read-only ingested facets
(task, calendar block, email-origin) as a Padhanam-native ``SAME_WORK`` edge: a
``:Unit`` anchor node, a thin ``:Facet`` reference node per facet (the id only,
never a copy of the cache row — the D164 ``:Lever`` rule), and a
``(:Facet)-[:SAME_WORK]->(:Unit)`` edge carrying the inference's confidence,
status, and basis.

It is a *sibling* of ``GraphRepositoryPort`` / ``OutcomeGraphPort``: a new
node-and-edge family on the same ``TenantScopedNeo4jSession`` wrapper (the single
Cypher surface fenced by the ``neo4j-confined`` contract and the AST enforcement
test), so no raw driver call enters domain code.

The port is goal-agnostic at the graph boundary: it speaks of units and facets
in primitive terms (ids, the facet-type string, the confidence/status/basis edge
properties). The daily-driver context owns the *unit* concept and consumes this
through its own ``UnitGraphPort`` + an apps-composition-root bridge (the
``GoalGraphPort`` precedent).

Correlation is *derived state* (D155): ``replace_units`` swaps the tenant's whole
facet/edge set on each run so stale links never accumulate, while preserving
``:Unit`` nodes whose deterministic id persists (so P19's goal facet survives a
re-run). Every node and edge carries ``tenant_id`` + ``jurisdiction`` and is
reached only through the tenant-scoped wrapper (D63/D64).

Errors reuse ``GraphRepositoryError`` / ``GraphRepositoryConfigurationError``
from ``graph_repository_port`` so callers handle one error taxonomy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence
from uuid import UUID

from shared_kernel import TenantContext


@dataclass(frozen=True)
class FacetLinkWrite:
    """One facet's membership to write — the ``SAME_WORK`` edge's payload."""

    facet_type: str
    facet_id: UUID
    confidence: float
    status: str
    basis: str


@dataclass(frozen=True)
class UnitWrite:
    """One unit to write: its deterministic id plus every facet link."""

    unit_id: UUID
    links: tuple[FacetLinkWrite, ...]


@dataclass(frozen=True)
class FacetLinkRecord:
    """One facet's membership as read back from the graph (thin — id only)."""

    facet_type: str
    facet_id: UUID
    confidence: float
    status: str
    basis: str


@dataclass(frozen=True)
class UnitGraphRecord:
    """One unit with all its facet links as read from the graph (D168)."""

    unit_id: UUID
    links: tuple[FacetLinkRecord, ...]


class UnitGraphPort(Protocol):
    """Typed work-unit-graph capability on the shared Neo4j instance (D168)."""

    async def replace_units(
        self,
        *,
        tenant_context: TenantContext,
        units: Sequence[UnitWrite],
    ) -> None:
        """Replace the tenant's whole unit subgraph with ``units`` (D168).

        Derived state (D155): deletes the tenant's ``:Facet`` nodes and
        ``SAME_WORK`` edges, prunes ``:Unit`` nodes no longer in ``units``
        (DETACH, so a dissolved unit's future goal edge goes with it), then
        MERGEs each unit (preserving the ``:Unit`` ``created_at`` for ids that
        persist) plus its facets and edges. Stores only ids + edge properties —
        never the facet's title.
        """
        ...

    async def list_units(
        self,
        *,
        tenant_context: TenantContext,
    ) -> Sequence[UnitGraphRecord]:
        """Return every unit with its facet edges for the bound tenant, ordered
        by unit id. Cross-tenant rows never surface (the wrapper binds
        ``tenant_id`` into every predicate)."""
        ...


__all__ = [
    "FacetLinkRecord",
    "FacetLinkWrite",
    "UnitGraphPort",
    "UnitGraphRecord",
    "UnitWrite",
]
