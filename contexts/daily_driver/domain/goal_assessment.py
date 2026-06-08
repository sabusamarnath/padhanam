"""Goal-aligned assessment — the moat read (D169, D166, assess-not-replace).

Padhanam overlays the layer no source tool holds: which goal the work serves, and
whether work is adrift of every goal or a goal adrift of all work. This module is
pure domain (D16): the application layer reads the units, goals, and commitment
names; these functions infer the goal facet and compute the two reads.

The goal-facet inference is **confidence-tiered** (the recall-over-precision call,
D169): both reads fire on the *absence* of a unit→goal edge, so a missed edge is a
false orphan and a false neglect — the read crying wolf. So:

- **confirmed** — a unit-facet title matches one of the goal's *lever-commitment*
  names (the precise commitment bridge: a calendar block "German practice" is the
  same work as the "German practice" commitment, which is the German goal's lever).
- **candidate** — a lean title-keyword match against the goal's *name* (recall),
  surfaced recommendation-shaped ("this looks like it serves German — link it?"),
  deliberately not an inference engine.

A unit is orphan only when **neither** a confirmed nor a candidate edge exists, so
orphan means orphan. The homeostatic/owed clause (D166) is honoured by maintenance
units candidate-linking to a homeostatic goal rather than reading as orphan
(dormant until such a goal is seeded).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from contexts.daily_driver.domain.goal import Goal
from contexts.daily_driver.domain.unit_view import UnitView
from contexts.daily_driver.domain.work_unit import LinkStatus, normalise_title

DEFAULT_GOAL_CONFIDENCE_FLOOR = 0.8
_CONFIRMED_CONFIDENCE = 0.9
_CANDIDATE_CONFIDENCE = 0.5
# A token must be at least this long to carry a candidate keyword match — keeps
# the lean matcher from firing on stopword-shaped fragments ("get", "the").
_MIN_KEYWORD_LEN = 4


@dataclass(frozen=True)
class GoalEdge:
    """An inferred unit→goal facet (the ``SERVES`` edge's payload)."""

    unit_id: UUID
    outcome_id: UUID
    confidence: float
    status: LinkStatus
    basis: str


@dataclass(frozen=True)
class OrphanUnit:
    """A unit of work pointing at no goal — recommendation-shaped (D169, D166)."""

    unit_id: UUID
    title: str
    facet_count: int
    is_correlated: bool
    reason: str


@dataclass(frozen=True)
class NeglectedGoal:
    """A goal nothing in the plan points at — recommendation-shaped (D169)."""

    outcome_id: UUID
    name: str
    reason: str


@dataclass(frozen=True)
class GoalAssessment:
    """The two moat reads, surfaced together."""

    orphan_work: tuple[OrphanUnit, ...]
    neglected_goals: tuple[NeglectedGoal, ...]


def _goal_commitment_ids(goal: Goal) -> tuple[UUID, ...]:
    """Every Postgres commitment id that serves as a lever for the goal."""
    ids: list[UUID] = []
    if goal.lever_commitment_id is not None:
        ids.append(goal.lever_commitment_id)
    ids.extend(step.commitment_id for step in goal.steps)
    return tuple(ids)


def _unit_titles(unit: UnitView) -> tuple[str, ...]:
    """The unit's present facet titles, normalised (skips removed references)."""
    return tuple(
        normalise_title(f.title)
        for f in unit.facets
        if f.present and normalise_title(f.title)
    )


def _keyword_match(unit_title: str, goal_name: str) -> bool:
    """Lean candidate match: substring either direction, or a shared long token.

    Deliberately simple (D169 — not an inference engine). Single-word goals
    (German, Esperanto, marathon) match by substring; multi-word goals match
    conservatively via a shared significant token.
    """
    if not unit_title or not goal_name:
        return False
    if goal_name in unit_title or unit_title in goal_name:
        return True
    unit_tokens = {t for t in unit_title.split() if len(t) >= _MIN_KEYWORD_LEN}
    goal_tokens = {t for t in goal_name.split() if len(t) >= _MIN_KEYWORD_LEN}
    return bool(unit_tokens & goal_tokens)


def infer_goal_edges(
    units: tuple[UnitView, ...],
    goals: tuple[Goal, ...],
    commitment_names: dict[UUID, str],
    *,
    confidence_floor: float = DEFAULT_GOAL_CONFIDENCE_FLOOR,
) -> tuple[GoalEdge, ...]:
    """Infer the unit→goal facet for every unit, confidence-tiered (D169).

    For each (unit, goal): a unit-facet title that matches one of the goal's
    lever-commitment names yields a ``confirmed`` edge; failing that, a lean
    keyword match against the goal name yields a ``candidate`` edge. A unit can
    serve more than one goal. Deterministic ordering (unit then goal) for a
    reproducible result.
    """
    edges: list[GoalEdge] = []
    for unit in units:
        titles = _unit_titles(unit)
        if not titles:
            continue
        for goal in goals:
            lever_names = [
                normalise_title(commitment_names[cid])
                for cid in _goal_commitment_ids(goal)
                if cid in commitment_names and commitment_names[cid]
            ]
            confirmed = any(
                t == lever for t in titles for lever in lever_names if lever
            )
            if confirmed:
                edges.append(
                    GoalEdge(
                        unit_id=unit.unit_id,
                        outcome_id=goal.id,
                        confidence=_CONFIRMED_CONFIDENCE,
                        status=LinkStatus.CONFIRMED,
                        basis="commitment",
                    )
                )
                continue
            goal_name = normalise_title(goal.name)
            if any(_keyword_match(t, goal_name) for t in titles):
                status = (
                    LinkStatus.CONFIRMED
                    if _CANDIDATE_CONFIDENCE >= confidence_floor
                    else LinkStatus.CANDIDATE
                )
                edges.append(
                    GoalEdge(
                        unit_id=unit.unit_id,
                        outcome_id=goal.id,
                        confidence=_CANDIDATE_CONFIDENCE,
                        status=status,
                        basis="goal-name",
                    )
                )
    return tuple(edges)


def assess_goals(
    units: tuple[UnitView, ...],
    goals: tuple[Goal, ...],
    edges: tuple[GoalEdge, ...],
) -> GoalAssessment:
    """Compute the two moat reads from the units, goals, and goal edges (D169).

    Orphan work = a unit with no outgoing ``SERVES`` edge (confirmed *or*
    candidate — a candidate is enough to mean "not orphan", the recall call).
    Neglected goal = a goal with no incoming ``SERVES`` edge. Both are
    recommendation-shaped (declarative, specific; the private-assistant
    discipline). Orphans are ordered cross-tool-units-first (the genuine work
    most likely to deserve a goal leads; the reverse-Kano restraint against a
    noisy read), then by title.
    """
    units_with_edge = {e.unit_id for e in edges}
    goals_with_edge = {e.outcome_id for e in edges}

    orphans = [
        OrphanUnit(
            unit_id=unit.unit_id,
            title=unit.title,
            facet_count=len(unit.facets),
            is_correlated=unit.is_correlated,
            reason=f"“{unit.title}” points at no goal you're tracking.",
        )
        for unit in units
        if unit.unit_id not in units_with_edge
    ]
    orphans.sort(key=lambda o: (0 if o.is_correlated else 1, o.title.lower()))

    neglected = tuple(
        NeglectedGoal(
            outcome_id=goal.id,
            name=goal.name,
            reason=f"Nothing in your plan points at “{goal.name}”.",
        )
        for goal in goals
        if goal.id not in goals_with_edge
    )
    return GoalAssessment(
        orphan_work=tuple(orphans), neglected_goals=neglected
    )


__all__ = [
    "DEFAULT_GOAL_CONFIDENCE_FLOOR",
    "GoalAssessment",
    "GoalEdge",
    "NeglectedGoal",
    "OrphanUnit",
    "assess_goals",
    "infer_goal_edges",
]
