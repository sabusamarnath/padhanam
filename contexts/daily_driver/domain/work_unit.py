"""Work-unit correlation domain (D168, D166).

A *unit of work* is one thing seen from up to four facets (D166): the origin in
a message, the tracking in a task, the time in a calendar block, the purpose in
a native goal. P18 correlates the first three — the read-only ingested caches —
into units by a title-and-time inference and records the Padhanam-native
same-work edge in the graph. The goal facet is P19.

This module is pure domain (D16): the matcher ``correlate_facets`` is a
deterministic function over facet projections; the application layer reads the
caches (the stores decrypt on read, so the matcher sees plaintext titles) and
writes the result to the graph through a consumer port. The correlation is
*derived state* (D155): re-running over the same caches yields the same units,
because unit identity is deterministic in the anchor facet.

The inference is **high-precision and confirm-not-assume** (D166): facets sharing
a normalised title correlate; a corroborating time anchor confirms the link
(auto-linked), while a title match without time corroboration is surfaced as a
*candidate* (not auto-linked). The anchor facet that defines a unit always links
confirmed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import NAMESPACE_URL, UUID, uuid5

# Sort sentinel for an untimed facet — orders after every real timestamp so
# timed facets pair first. Timezone-aware to stay comparable with aware values.
_UNTIMED = datetime(9999, 12, 31, tzinfo=timezone.utc)

# Defaults for the inference; the application layer may override from config.
DEFAULT_CONFIDENCE_FLOOR = 0.8
DEFAULT_TIME_WINDOW_DAYS = 7

# Confidence the inference assigns. The anchor's self-link is certain; a
# title-and-time match is high; a title-only match (no corroborating time) is
# below the floor, so it surfaces as a candidate rather than auto-linking.
_ANCHOR_CONFIDENCE = 1.0
_TITLE_AND_TIME_CONFIDENCE = 0.9
_TITLE_ONLY_CONFIDENCE = 0.6


class FacetType(str, Enum):
    """The kind of cache a facet references."""

    TASK = "task"
    MEETING = "meeting"
    EMAIL = "email"


# Anchor priority — the facet type that anchors a unit's deterministic identity.
# A unit's anchor is its highest-priority facet (task > meeting > email),
# tie-broken by facet id, so ``unit_id`` is stable across re-correlation as long
# as the anchor persists (D168 idempotency + P19 stability).
_ANCHOR_PRIORITY = {
    FacetType.TASK: 0,
    FacetType.MEETING: 1,
    FacetType.EMAIL: 2,
}


class LinkStatus(str, Enum):
    """How a facet's membership in its unit is treated."""

    CONFIRMED = "confirmed"  # at/above the floor — auto-linked
    CANDIDATE = "candidate"  # below the floor — surfaced, not auto-linked


@dataclass(frozen=True)
class WorkFacet:
    """A read-only projection of one cache row — the matcher's input.

    Carries only what the title-and-time inference needs plus the stable id the
    thin ``:Facet`` reference node points at (never a copy of the cache row,
    D164). ``occurred_at`` is the facet's time anchor (task due, meeting start,
    email received); ``None`` when the source has none.
    """

    facet_type: FacetType
    facet_id: UUID
    title: str
    occurred_at: datetime | None


@dataclass(frozen=True)
class FacetLink:
    """One facet's membership in a unit — the ``SAME_WORK`` edge's payload."""

    facet: WorkFacet
    confidence: float
    status: LinkStatus
    basis: str


@dataclass(frozen=True)
class UnitFacetRef:
    """One facet's membership as read back from the graph (thin — id only).

    The graph stores only the cache row's id; the units reader joins each ref
    back to its cache for the title at display time.
    """

    facet_type: FacetType
    facet_id: UUID
    confidence: float
    status: LinkStatus
    basis: str


@dataclass(frozen=True)
class UnitRecord:
    """One correlated unit as read back from the graph (D168) — thin facets."""

    unit_id: UUID
    facets: tuple[UnitFacetRef, ...]


@dataclass(frozen=True)
class WorkUnit:
    """A correlated unit of work: an anchor facet plus every facet linked to it.

    ``links`` includes the anchor's own (confirmed) link, so the graph write is
    uniform — every facet, anchor included, becomes a ``:Facet`` node with a
    ``SAME_WORK`` edge to the ``:Unit``.
    """

    unit_id: UUID
    anchor: WorkFacet
    links: tuple[FacetLink, ...]

    @property
    def is_correlated(self) -> bool:
        """True when the unit binds more than its anchor facet."""
        return len(self.links) > 1


_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalise_title(title: str) -> str:
    """Normalise a facet title for matching: lowercase, alnum-only, collapsed.

    Deterministic so the matcher is reproducible. An empty result (a blank or
    punctuation-only title) does not correlate — there is nothing to match on.
    """
    return _NON_ALNUM.sub(" ", title.lower()).strip()


def _anchor_of(facets: tuple[WorkFacet, ...]) -> WorkFacet:
    """The unit's anchor: highest-priority type, tie-broken by facet id."""
    return min(
        facets,
        key=lambda f: (_ANCHOR_PRIORITY[f.facet_type], str(f.facet_id)),
    )


def _unit_id_for(anchor: WorkFacet, *, tenant_id: UUID) -> UUID:
    """Deterministic unit identity in the anchor facet (D168).

    Stable across re-correlation while the anchor persists, so P19's goal facet
    can attach to a unit that survives a re-run.
    """
    return uuid5(
        NAMESPACE_URL,
        f"unit:{tenant_id}:{anchor.facet_type.value}:{anchor.facet_id}",
    )


def _infer_link(
    facet: WorkFacet,
    anchor: WorkFacet,
    *,
    confidence_floor: float,
    time_window_days: int,
) -> FacetLink:
    """Score a non-anchor facet's membership against the unit's anchor.

    A corroborating time anchor (both facets timed, within the window) confirms
    the link; a title match without time corroboration is a candidate (D166
    confirm-not-assume).
    """
    if _within_window(facet, anchor, time_window_days=time_window_days):
        confidence, basis = _TITLE_AND_TIME_CONFIDENCE, "title+time"
    else:
        confidence, basis = _TITLE_ONLY_CONFIDENCE, "title"
    status = (
        LinkStatus.CONFIRMED
        if confidence >= confidence_floor
        else LinkStatus.CANDIDATE
    )
    return FacetLink(
        facet=facet, confidence=confidence, status=status, basis=basis
    )


def _within_window(a: WorkFacet, b: WorkFacet, *, time_window_days: int) -> bool:
    if a.occurred_at is None or b.occurred_at is None:
        return False
    return abs((a.occurred_at - b.occurred_at).days) <= time_window_days


def _time_distance_days(a: WorkFacet, b: WorkFacet) -> float:
    """Absolute day distance, or infinity when either facet is untimed."""
    if a.occurred_at is None or b.occurred_at is None:
        return float("inf")
    return abs((a.occurred_at - b.occurred_at).days)


def _single_facet_unit(facet: WorkFacet, *, tenant_id: UUID) -> WorkUnit:
    return WorkUnit(
        unit_id=_unit_id_for(facet, tenant_id=tenant_id),
        anchor=facet,
        links=(
            FacetLink(
                facet=facet,
                confidence=_ANCHOR_CONFIDENCE,
                status=LinkStatus.CONFIRMED,
                basis="anchor",
            ),
        ),
    )


def _units_from_title_group(
    group: tuple[WorkFacet, ...],
    *,
    tenant_id: UUID,
    confidence_floor: float,
    time_window_days: int,
) -> list[WorkUnit]:
    """Build units from facets that share a normalised title.

    A *unit of work* (D166) binds at most one facet per type — the cross-tool
    correlation is the differentiator, not collapsing same-type duplicates.
    So facets are bucketed by type; if only one type is present (e.g. the
    recurring instances of one calendar event), each facet is its own
    single-facet unit. When two or more types are present, each facet of the
    highest-priority type anchors a unit and consumes the *nearest-in-time*
    available facet of each other type (one-to-one, high-precision); any
    unconsumed facets become their own single-facet units.
    """
    buckets: dict[FacetType, list[WorkFacet]] = {}
    for facet in group:
        buckets.setdefault(facet.facet_type, []).append(facet)
    for facets in buckets.values():
        facets.sort(key=lambda f: (f.occurred_at or _UNTIMED, str(f.facet_id)))

    if len(buckets) == 1:
        return [_single_facet_unit(f, tenant_id=tenant_id) for f in group]

    anchor_type = min(buckets, key=lambda t: _ANCHOR_PRIORITY[t])
    other_types = [t for t in buckets if t != anchor_type]
    consumed: set[UUID] = set()
    units: list[WorkUnit] = []
    for anchor in buckets[anchor_type]:
        links = [
            FacetLink(
                facet=anchor,
                confidence=_ANCHOR_CONFIDENCE,
                status=LinkStatus.CONFIRMED,
                basis="anchor",
            )
        ]
        for other_type in other_types:
            available = [
                f for f in buckets[other_type] if f.facet_id not in consumed
            ]
            if not available:
                continue
            match = min(available, key=lambda f: _time_distance_days(f, anchor))
            consumed.add(match.facet_id)
            links.append(
                _infer_link(
                    match,
                    anchor,
                    confidence_floor=confidence_floor,
                    time_window_days=time_window_days,
                )
            )
        units.append(
            WorkUnit(
                unit_id=_unit_id_for(anchor, tenant_id=tenant_id),
                anchor=anchor,
                links=tuple(links),
            )
        )
    # Any non-anchor-type facets not paired become their own units.
    for other_type in other_types:
        for facet in buckets[other_type]:
            if facet.facet_id not in consumed:
                units.append(_single_facet_unit(facet, tenant_id=tenant_id))
    return units


def correlate_facets(
    facets: tuple[WorkFacet, ...],
    *,
    tenant_id: UUID,
    confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR,
    time_window_days: int = DEFAULT_TIME_WINDOW_DAYS,
) -> tuple[WorkUnit, ...]:
    """Correlate facets into units of work by a title-and-time inference (D168).

    Facets sharing a normalised title are candidates for one *unit of work*, but
    a unit binds at most one facet per type (D166): the cross-tool link is the
    differentiator. Same-type duplicates of a title (e.g. recurring calendar
    instances) do **not** collapse — each is its own single-facet unit. A facet
    whose title does not normalise (blank/punctuation-only) or whose title is
    unique is its own single-facet unit too, so every facet belongs to exactly
    one unit (P19 can then flag an orphan). Units are returned ordered by
    ``unit_id`` for a deterministic result.
    """
    groups: dict[str, list[WorkFacet]] = {}
    singletons: list[WorkFacet] = []
    for facet in facets:
        key = normalise_title(facet.title)
        if not key:
            singletons.append(facet)
        else:
            groups.setdefault(key, []).append(facet)

    units: list[WorkUnit] = []
    for members in groups.values():
        units.extend(
            _units_from_title_group(
                tuple(members),
                tenant_id=tenant_id,
                confidence_floor=confidence_floor,
                time_window_days=time_window_days,
            )
        )
    for facet in singletons:
        units.append(_single_facet_unit(facet, tenant_id=tenant_id))
    units.sort(key=lambda u: str(u.unit_id))
    return tuple(units)


__all__ = [
    "DEFAULT_CONFIDENCE_FLOOR",
    "DEFAULT_TIME_WINDOW_DAYS",
    "FacetLink",
    "FacetType",
    "LinkStatus",
    "UnitFacetRef",
    "UnitRecord",
    "WorkFacet",
    "WorkUnit",
    "correlate_facets",
    "normalise_title",
]
