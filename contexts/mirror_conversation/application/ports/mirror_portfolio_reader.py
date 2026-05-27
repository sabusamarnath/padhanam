"""MirrorPortfolioReader consumer port (P14, S52).

The mirror-conversation cell's cross-context read surface into the
portfolio context. Per D16/D17/D28 the cell cannot import
``contexts.portfolio.application`` directly; it consumes this
consumer-defined Protocol, and the ``apps/`` composition root provides
the adapter that wraps the portfolio reads.

The port carries the read shapes mirror-conversation needs at P14:

- ``list_cases``: enumerate the operator's cases with the discriminators
  needed for the operator-facing listing (title, last activity, data-
  point count).
- ``get_case_detail``: load a case plus its data points (with revision
  history) for the ShowCase + DrillDownToChild flows.
- ``get_data_point``: load a single data point with its revision
  history for the ShowDataPoint flow.
- ``find_cases``: enumerate cases for title-resolution (used by
  ShowCase + DrillDownToChild + ShowParent when the user names an
  artefact by natural-language reference).

The DTOs (``MirrorCaseSummary``, ``MirrorCaseDetail``,
``MirrorDataPoint``, ``MirrorDataPointSummary``) are mirror-conversation-
owned shapes the wiring adapter translates portfolio-context entities
into. Keeping the DTOs at the cell's context preserves the cross-
context discipline and lets the cell evolve its read shape without
touching portfolio domain types.

Framework-free per D16 — stdlib plus shared_kernel only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from shared_kernel import ActorContext


@dataclass(frozen=True)
class MirrorCaseSummary:
    """Operator-facing summary of one Case for listing and resolution."""

    case_id: UUID
    title: str
    case_status: str
    created_at: datetime
    last_activity_at: datetime
    data_point_count: int


@dataclass(frozen=True)
class MirrorDataPointSummary:
    """Operator-facing summary of one DataPoint within a case."""

    data_point_id: UUID
    case_id: UUID
    data_point_type: str
    label: str
    created_at: datetime


@dataclass(frozen=True)
class MirrorDataPoint:
    """Full DataPoint detail for the ShowDataPoint flow."""

    data_point_id: UUID
    case_id: UUID
    data_point_type: str
    current_value: dict[str, Any]
    created_at: datetime
    revision_count: int


@dataclass(frozen=True)
class MirrorCaseDetail:
    """A Case plus its DataPoints; the response shape for ShowCase."""

    case: MirrorCaseSummary
    data_points: tuple[MirrorDataPointSummary, ...]


class MirrorPortfolioReader(Protocol):
    """Read-side consumer port for the mirror-conversation cell (P14, S52)."""

    async def list_cases(
        self, *, actor: ActorContext, limit: int = 50
    ) -> tuple[MirrorCaseSummary, ...]:
        """Return up to ``limit`` cases for the tenant, newest first."""
        ...

    async def get_case_detail(
        self, *, actor: ActorContext, case_id: UUID
    ) -> MirrorCaseDetail | None:
        """Return a case with its data points, or ``None`` when absent."""
        ...

    async def get_data_point(
        self, *, actor: ActorContext, data_point_id: UUID
    ) -> MirrorDataPoint | None:
        """Return a single data point with revision-count summary."""
        ...

    async def find_cases(
        self, *, actor: ActorContext
    ) -> tuple[MirrorCaseSummary, ...]:
        """Enumerate cases for title-resolution (broader page-size than list)."""
        ...


__all__ = [
    "MirrorCaseDetail",
    "MirrorCaseSummary",
    "MirrorDataPoint",
    "MirrorDataPointSummary",
    "MirrorPortfolioReader",
]
