"""Unit-view projection — the rendered work-unit (D168, D166).

The correlated units are read back from the graph as thin references (ids only);
this module joins each reference to its cache facet (title + time) and assembles
the display projection the units surface renders. Pure domain (D16): the
application layer supplies the graph records and the facet lookup; the assembler
is deterministic.

A unit is shown *as a unit* — one row carrying its facets (the task, the calendar
block, the email-origin) — rather than the facets shown as separate rows. A
below-floor facet is a ``candidate`` and is marked as such so the surface can
present it as a suggestion-to-confirm, not an asserted link (D166
confirm-not-assume; the private-assistant suggestion-as-question discipline).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.daily_driver.domain.work_unit import (
    FacetType,
    LinkStatus,
    UnitRecord,
    WorkFacet,
)

# Display order for a unit's facets and for choosing its headline title.
_FACET_ORDER = {FacetType.TASK: 0, FacetType.MEETING: 1, FacetType.EMAIL: 2}

_REMOVED_TITLE = "(removed from source)"


@dataclass(frozen=True)
class UnitFacetView:
    """One facet of a rendered unit — its reference joined to its cache title."""

    facet_type: FacetType
    facet_id: UUID
    title: str
    occurred_at: datetime | None
    status: LinkStatus
    confidence: float
    basis: str
    present: bool  # False when the cache row is gone (a stale reference)


@dataclass(frozen=True)
class UnitView:
    """A rendered unit of work: a headline plus its facets (D168)."""

    unit_id: UUID
    title: str
    facets: tuple[UnitFacetView, ...]

    @property
    def is_correlated(self) -> bool:
        """True when the unit binds more than one facet — a cross-tool unit."""
        return len(self.facets) > 1

    @property
    def has_candidate(self) -> bool:
        """True when a below-floor facet is surfaced for confirmation."""
        return any(f.status is LinkStatus.CANDIDATE for f in self.facets)


def _facet_sort_key(facet: UnitFacetView) -> tuple[int, int, str]:
    # Confirmed before candidate; then by facet type; then by title.
    status_rank = 0 if facet.status is LinkStatus.CONFIRMED else 1
    return (status_rank, _FACET_ORDER[facet.facet_type], facet.title.lower())


def build_unit_views(
    units: tuple[UnitRecord, ...],
    facets_by_key: dict[tuple[FacetType, UUID], WorkFacet],
) -> tuple[UnitView, ...]:
    """Assemble the rendered units from graph records + a cache facet lookup.

    ``facets_by_key`` maps ``(facet_type, facet_id)`` to the cache projection
    (title + time). A reference with no cache row (a row deleted since the last
    correlation) renders with a placeholder title and ``present=False`` rather
    than vanishing, so the count stays honest until the next re-correlation
    prunes it. Units are ordered correlated-first (the cross-tool differentiator
    leads), then by title.
    """
    views: list[UnitView] = []
    for record in units:
        facet_views: list[UnitFacetView] = []
        for ref in record.facets:
            facet = facets_by_key.get((ref.facet_type, ref.facet_id))
            facet_views.append(
                UnitFacetView(
                    facet_type=ref.facet_type,
                    facet_id=ref.facet_id,
                    title=facet.title if facet is not None else _REMOVED_TITLE,
                    occurred_at=facet.occurred_at if facet is not None else None,
                    status=ref.status,
                    confidence=ref.confidence,
                    basis=ref.basis,
                    present=facet is not None,
                )
            )
        facet_views.sort(key=_facet_sort_key)
        headline = facet_views[0].title if facet_views else _REMOVED_TITLE
        views.append(
            UnitView(
                unit_id=record.unit_id,
                title=headline,
                facets=tuple(facet_views),
            )
        )
    views.sort(key=lambda u: (0 if u.is_correlated else 1, u.title.lower()))
    return tuple(views)


__all__ = ["UnitFacetView", "UnitView", "build_unit_views"]
