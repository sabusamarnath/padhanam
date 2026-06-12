"""The neutral input a matcher MetricCalculator measures (D185).

The matcher's edges are projected to this label-free shape at the composition
root (``apps/``) — each edge classified into the structural categories the
metrics count, the whole set of unit ids carried so orphans (units with no edge)
are computable. This context never sees ``daily_driver``'s ``GoalEdge``; it sees
only these booleans and ids, so it stays self-contained per the independence
contracts (D17) and the calculator stays a generic structural aggregator.

Pure domain (D16): stdlib only, no I/O, no content (no titles/senders/subjects).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class EdgeSample:
    """One SERVES edge, classified into the structural categories the metrics
    count. ``is_candidate`` / ``is_confirmed`` are mutually exclusive (the edge's
    link status); ``is_single_signal`` marks the weak keyword-on-name basis."""

    unit_id: UUID
    is_single_signal: bool
    is_candidate: bool
    is_confirmed: bool


@dataclass(frozen=True)
class MatcherQualitySample:
    """The matcher's output for one correlate run, label-free.

    ``edges`` is every SERVES edge classified; ``unit_ids`` is *every* unit the
    matcher considered (not only the linked ones), so the orphan count — units
    with no edge — is ``len(unit_ids)`` minus the linked units.
    """

    edges: tuple[EdgeSample, ...]
    unit_ids: frozenset[UUID]


__all__ = ["EdgeSample", "MatcherQualitySample"]
