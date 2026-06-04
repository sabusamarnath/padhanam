"""Consumer-defined port for OPEN Cases (D157, D17 cross-context seam).

The daily-driver context does not import the portfolio context. It
declares the read it needs — the tenant's OPEN Cases as the local
``OpenCase`` projection — and an ``apps/`` wiring adapter implements the
port by composing the portfolio ``list_cases`` use case (the legal
cross-context seam per D17, mirroring the daily-briefing
``DailyBriefingReader`` precedent). Ports layer is pure per D16.
"""

from __future__ import annotations

from typing import Protocol

from contexts.daily_driver.domain.today_item import OpenCase
from shared_kernel import ActorContext


class OpenCasesReader(Protocol):
    """Read port returning the actor's OPEN portfolio Cases as projections."""

    async def list_open_cases(
        self, *, actor: ActorContext
    ) -> tuple[OpenCase, ...]:
        """Return the tenant's OPEN Cases (current-state snapshot)."""
        ...


__all__ = ["OpenCasesReader"]
