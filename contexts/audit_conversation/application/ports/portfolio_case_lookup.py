"""PortfolioCaseLookup consumer port (P14, S51).

Cross-context reads from the portfolio context go through a consumer-
defined Protocol at the audit-conversation application layer; the
``apps/`` composition root provides the adapter that wraps
``contexts.portfolio`` reads. Mirrors the messaging context's
PortfolioGateway pattern (S46) for case lookup, but scoped to the
single read audit-conversation needs (case-by-title resolution for
``FindByCase`` intents).

Per pre-write reconciliation at S51 commit 3, audit-conversation does
not consume the messaging context's PortfolioGateway directly because
cross-context application imports are forbidden by the
``contexts-independent-application`` import-linter contract (D16, D17,
D28). Each consuming context defines its own minimal consumer port.

Framework-free; stdlib-only Protocol shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from shared_kernel import ActorContext


@dataclass(frozen=True)
class AuditCaseSummary:
    """The minimal Case summary audit-conversation needs for title resolution."""

    case_id: UUID
    title: str


class PortfolioCaseLookup(Protocol):
    """Read-side consumer port for portfolio case discovery.

    The audit-conversation cell calls ``find_cases`` when a ``FindByCase``
    or ``FindByCombination`` intent's case_reference needs resolution to
    a concrete ``case_id`` for filtering the audit query. The cell
    re-uses ``resolve_target`` (messaging.application.target_resolution)
    against the returned ``AuditCaseSummary`` tuple to produce a single
    matched id (Case 1) or a candidate list (Case 2 resolution-
    ambiguity per D139).
    """

    async def find_cases(
        self, *, actor: ActorContext
    ) -> tuple[AuditCaseSummary, ...]:
        """Return the operator's tenant's cases for title resolution."""
        ...


__all__ = ["AuditCaseSummary", "PortfolioCaseLookup"]
