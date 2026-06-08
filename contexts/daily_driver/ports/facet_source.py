"""FacetSource — the consumer port over the read-only ingested caches (D168, D17).

The correlation use case needs every correlation-candidate facet — open tasks,
calendar meetings, email-origins — as the matcher's ``WorkFacet`` projection.
The daily-driver context cannot import the tasks / calendar / email contexts
(D17 independence), so it declares this consumer port; an ``apps/`` wiring
adapter composes the three stores (which decrypt on read), maps each row onto a
``WorkFacet``, and returns the flat list. Ports layer is pure per D16.
"""

from __future__ import annotations

from typing import Protocol

from contexts.daily_driver.domain.work_unit import WorkFacet
from shared_kernel import ActorContext


class FacetSource(Protocol):
    """Read port returning the actor's correlation-candidate facets."""

    async def list_facets(self, *, actor: ActorContext) -> tuple[WorkFacet, ...]:
        """Return every facet to correlate (tasks, meetings, emails)."""
        ...


__all__ = ["FacetSource"]
