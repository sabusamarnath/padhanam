"""PortfolioGateway consumer port — the cell's single portfolio seam (S46).

The manual entry cell must both *read* portfolio state (to resolve a
natural-language reference to a Case or DataPoint) and *write* it (to
drive an intake-canonical orchestration). Per the D16/D17/D28
cross-context contract the messaging application layer cannot import
``contexts.intake`` or ``contexts.portfolio`` directly; it defines
the shape it needs here, and the ``apps/`` composition layer provides
the adapter.

S46 pre-write reconciliation Finding D settled the port shape: one
``PortfolioGateway`` carrying both the resolution reads and the three
orchestration writes, rather than separate read and per-operation
write ports. The cell has a single collaborator concern — interact
with the portfolio context — and one gateway reads more naturally at
the dispatch level than method-routing across four interfaces. Future
portfolio operations the cell needs extend this Protocol's method
surface (OCP) rather than adding new ports.

This module imports nothing from ``contexts.intake`` or
``contexts.portfolio`` — the DTOs are messaging-context-owned,
mirroring the producer's output at the type level. The structural
duplication is the intentional cost of the D17 boundary; the wiring
adapter does field-for-field translation. The shape follows the
consumer-port-plus-wiring-adapter precedent at
``contexts/intake/application/ports/portfolio_writer.py``.

Ports layer is pure per D16 — stdlib plus shared_kernel only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from shared_kernel import ActorContext


@dataclass(frozen=True)
class CaseSummary:
    """A Case as the cell sees it for target resolution.

    ``title`` is the human label ``resolve_target`` scores a
    natural-language case reference against.
    """

    case_id: UUID
    title: str


@dataclass(frozen=True)
class DataPointSummary:
    """A DataPoint as the cell sees it for target resolution.

    ``label`` is the human-readable string ``resolve_target`` scores
    a natural-language data-point reference against — built by the
    adapter from the DataPoint's current value.
    """

    data_point_id: UUID
    case_id: UUID
    data_point_type: str
    label: str


@dataclass(frozen=True)
class CaseWriteOutcome:
    """The result of a create-case orchestration.

    Carries the IDs the cell cites in its D131 response —
    ``intake_id`` (cited intake record) and ``case_id`` (cited
    artefact).
    """

    case_id: UUID
    intake_id: UUID
    title: str


@dataclass(frozen=True)
class DataPointWriteOutcome:
    """The result of a create- or revise-data-point orchestration.

    ``assertion_ids`` is the DataPoint's full revision chain; the cell
    cites the DataPoint id as the artefact and the IntakeRecord id as
    the cited intake record in its D131 response.
    """

    data_point_id: UUID
    case_id: UUID
    intake_id: UUID
    assertion_ids: tuple[UUID, ...] = field(default_factory=tuple)


class PortfolioGateway(Protocol):
    """The manual entry cell's single seam to the portfolio context.

    ``find_cases`` / ``find_data_points`` are the resolution reads;
    ``create_case`` / ``create_data_point`` / ``revise_data_point``
    drive the intake-canonical orchestrations (``raw_text`` is the
    inbound message body the orchestration records as the IntakeRecord
    payload). The ``apps/``-layer adapter implements this Protocol,
    invoking the intake orchestrations and portfolio read use cases
    and translating their results into the DTOs above.
    """

    async def find_cases(
        self, *, actor: ActorContext
    ) -> tuple[CaseSummary, ...]:
        """Return the actor's tenant's cases for target resolution."""
        ...

    async def find_data_points(
        self, *, actor: ActorContext
    ) -> tuple[DataPointSummary, ...]:
        """Return the actor's tenant's data points for target resolution."""
        ...

    async def create_case(
        self, *, actor: ActorContext, raw_text: str, title: str
    ) -> CaseWriteOutcome:
        """Record an intake and create a Case; return the cited IDs."""
        ...

    async def create_data_point(
        self,
        *,
        actor: ActorContext,
        raw_text: str,
        case_id: UUID,
        data_point_type: str,
        value: dict[str, Any],
    ) -> DataPointWriteOutcome:
        """Record an intake and create a DataPoint on ``case_id``."""
        ...

    async def revise_data_point(
        self,
        *,
        actor: ActorContext,
        raw_text: str,
        data_point_id: UUID,
        value: dict[str, Any],
    ) -> DataPointWriteOutcome:
        """Record an intake and revise the DataPoint ``data_point_id``."""
        ...


__all__ = [
    "CaseSummary",
    "CaseWriteOutcome",
    "DataPointSummary",
    "DataPointWriteOutcome",
    "PortfolioGateway",
]
