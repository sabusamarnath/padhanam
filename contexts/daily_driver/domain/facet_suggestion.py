"""Missing-facet suggestions — the recommendation engine (D170, D166).

Padhanam suggests the facet a unit of work lacks: a *block* for a substantial
task with no calendar time, *satellite-work* for an event with no task (prep or
follow-up — never an event mirror), a *candidate task* for an email with no task.
Pure domain (D16): the application layer supplies the units, the goal facets, and
the cache facet projections; this function computes the suggestions at read time
(recommendation-shaped, never persisted, never written back).

The governing discipline is **credulity** (D170): over-suggestion is the failure
to watch — a surface that fires on every gap trains the user to ignore it (the
reverse-Kano shape). So the engine is gated hard:

- It fires only on units that **serve a goal** (the D169 SERVES facet — work that
  matters to something the user is trying to become). An orphan unit gets no
  suggestion; the remedy reads the goal shape.
- At most **one** suggestion per unit (the highest-value missing facet), so a
  multi-gap unit does not pile on.
- A *block* suggestion is withheld for an **atomic one-off** (a task with no due
  anchor) — only a substantial task earns the nudge.

Selective and confident, or silent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from contexts.daily_driver.domain.unit_view import UnitView
from contexts.daily_driver.domain.work_unit import FacetType


class SuggestionKind(str, Enum):
    """The missing facet a suggestion would fill (D170)."""

    BLOCK = "block"  # task with no time → block time for it
    SATELLITE_WORK = "satellite_work"  # event with no task → prep/follow-up
    CANDIDATE_TASK = "candidate_task"  # email with no task → turn into a task


@dataclass(frozen=True)
class FacetSuggestion:
    """One recommendation-shaped missing-facet suggestion (D170)."""

    unit_id: UUID
    kind: SuggestionKind
    subject: str  # the unit's headline the suggestion is about
    suggestion: str  # the suggestion-as-question prose (private-assistant D pattern)


def _present_types(unit: UnitView) -> set[FacetType]:
    return {f.facet_type for f in unit.facets if f.present}


def _has_due_anchor(unit: UnitView, facet_type: FacetType) -> bool:
    """True when a present facet of the type carries a time anchor (substantial)."""
    return any(
        f.present and f.facet_type is facet_type and f.occurred_at is not None
        for f in unit.facets
    )


def _suggest_for_unit(unit: UnitView) -> FacetSuggestion | None:
    """The single highest-value missing-facet suggestion for a unit, or None.

    Priority: a substantial task with no time (block) → an event with no task
    (satellite work) → an email with no task (candidate task). At most one, so a
    multi-gap unit does not nag.
    """
    types = _present_types(unit)
    title = unit.title

    if FacetType.TASK in types and FacetType.MEETING not in types:
        # Block time — but only for a substantial task (has a due anchor); an
        # atomic one-off is left alone (D170 scope-guard).
        if _has_due_anchor(unit, FacetType.TASK):
            return FacetSuggestion(
                unit_id=unit.unit_id,
                kind=SuggestionKind.BLOCK,
                subject=title,
                suggestion=f"Want to block time for “{title}”?",
            )
        return None

    if FacetType.MEETING in types and FacetType.TASK not in types:
        # Satellite work — prep or follow-up, NOT a task that mirrors the event.
        return FacetSuggestion(
            unit_id=unit.unit_id,
            kind=SuggestionKind.SATELLITE_WORK,
            subject=title,
            suggestion=f"Want to add prep or follow-up work for “{title}”?",
        )

    if (
        FacetType.EMAIL in types
        and FacetType.TASK not in types
        and FacetType.MEETING not in types
    ):
        return FacetSuggestion(
            unit_id=unit.unit_id,
            kind=SuggestionKind.CANDIDATE_TASK,
            subject=title,
            suggestion=f"Want to turn “{title}” into a task?",
        )

    return None


def suggest_missing_facets(
    units: tuple[UnitView, ...],
    goal_served_unit_ids: frozenset[UUID],
) -> tuple[FacetSuggestion, ...]:
    """Compute the missing-facet suggestions (D170), credulity-gated.

    Only units that serve a goal (``goal_served_unit_ids`` — the D169 SERVES
    facet) are considered, so the surface stays quiet on orphan work. Each
    qualifying unit yields at most one suggestion. Ordered by unit id for a
    deterministic result.
    """
    suggestions: list[FacetSuggestion] = []
    for unit in units:
        if unit.unit_id not in goal_served_unit_ids:
            continue
        suggestion = _suggest_for_unit(unit)
        if suggestion is not None:
            suggestions.append(suggestion)
    suggestions.sort(key=lambda s: str(s.unit_id))
    return tuple(suggestions)


__all__ = [
    "FacetSuggestion",
    "SuggestionKind",
    "suggest_missing_facets",
]
