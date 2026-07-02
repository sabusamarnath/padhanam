"""The act worklist — the pure substrate logic (D232).

An ``ActItem`` is one thing to act on, aggregated from six sources (the
pipeline next-best-action, warming steps due, stage-relative stale
qualification, commitments, calendar events, and open cases). The
application layer maps each source's read onto an ``ActItem``; this module
holds only the horizon math and the per-subject dedupe, so the substrate
logic is deterministic and testable.

A ``due_in_days`` of ``0`` or negative means *due today or overdue*; a
positive value is *upcoming* (days until it falls due). The three lens
controls are pure cuts over the substrate: **Today** = ``due_in_days <= 0``,
**Week** = ``due_in_days <= WEEK_DAYS``, **doing** = ``is_opportunity`` (the
live-opportunity items, the active board, no horizon cut).

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

# The six sources the substrate unions (D232).
SOURCE_PIPELINE = "pipeline"
SOURCE_WARMING = "warming"
SOURCE_QUALIFICATION = "qualification"
SOURCE_COMMITMENT = "commitment"
SOURCE_CALENDAR = "calendar"
SOURCE_CASE = "case"
ACT_SOURCES = (
    SOURCE_PIPELINE, SOURCE_WARMING, SOURCE_QUALIFICATION,
    SOURCE_COMMITMENT, SOURCE_CALENDAR, SOURCE_CASE,
)

# The Week horizon boundary: due within seven days (a day-8 item is excluded).
WEEK_DAYS = 7

# Horizon buckets (a rendering hint; the toggle filters on due_in_days).
HORIZON_OVERDUE = "overdue"
HORIZON_TODAY = "today"
HORIZON_WEEK = "week"
HORIZON_LATER = "later"


def horizon_of(due_in_days: int) -> str:
    """Bucket a due offset into a horizon label (D232). Today = due today or
    overdue; Week = within seven days; later = beyond the week."""
    if due_in_days < 0:
        return HORIZON_OVERDUE
    if due_in_days == 0:
        return HORIZON_TODAY
    if due_in_days <= WEEK_DAYS:
        return HORIZON_WEEK
    return HORIZON_LATER


@dataclass(frozen=True)
class ActItem:
    """One actionable item on the act worklist (D232).

    ``ref`` carries the source-specific routing/render payload (an opportunity's
    ``outcome_id``, a commitment's outcome-loop fields, a calendar item's
    ``start_at``) so the surface opens the right drawer without a second fetch;
    the substrate logic ignores it.
    """

    source: str
    subject_kind: str  # "opportunity" | "commitment" | "calendar" | "case"
    subject_id: str
    subject: str  # display label
    action: str  # the next-best-action / what-to-do line
    due_in_days: int  # <= 0 due today or overdue; > 0 upcoming
    is_opportunity: bool  # drives the doing (live-opportunity) filter
    ref: dict = field(default_factory=dict)

    @property
    def horizon(self) -> str:
        return horizon_of(self.due_in_days)


def build_act_worklist(items: Iterable[ActItem]) -> tuple[ActItem, ...]:
    """Dedupe the union per subject (most-overdue wins on a collision) and sort
    by urgency (D232). Two items on the same subject — a pipeline follow-up and a
    stale qualification field on one opportunity — collapse to the more overdue,
    so the worklist reads as one line per thing to act on, not a dump."""
    by_subject: dict[tuple[str, str], ActItem] = {}
    for it in items:
        key = (it.subject_kind, it.subject_id)
        current = by_subject.get(key)
        if current is None or it.due_in_days < current.due_in_days:
            by_subject[key] = it
    return tuple(
        sorted(
            by_subject.values(),
            key=lambda i: (i.due_in_days, i.subject.lower()),
        )
    )


__all__ = [
    "ACT_SOURCES", "ActItem", "HORIZON_LATER", "HORIZON_OVERDUE",
    "HORIZON_TODAY", "HORIZON_WEEK", "SOURCE_CALENDAR", "SOURCE_CASE",
    "SOURCE_COMMITMENT", "SOURCE_PIPELINE", "SOURCE_QUALIFICATION",
    "SOURCE_WARMING", "WEEK_DAYS", "build_act_worklist", "horizon_of",
]
