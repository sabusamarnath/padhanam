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
# A token carries a candidate keyword match unless it is a stopword (D172, the
# tier-one stopword filter replacing the old four-character length guard). Length
# is a bad proxy for signal: "job" is short and high-signal, "get" is short and
# noise — so the short high-signal word "job" links "Get a job" to "Job search",
# while a stopword like "get" stays suppressed at any length. Inspectable inline
# data, no dependency; extend from observed false matches.
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "to", "of", "in", "on", "at",
        "for", "with", "my", "your", "our", "get", "got", "do", "did",
        "doing", "be", "is", "are", "was", "this", "that", "these", "those",
        "it", "as", "by", "from", "into",
    }
)


@dataclass(frozen=True)
class GoalEdge:
    """An inferred unit→goal facet (the ``SERVES`` edge's payload)."""

    unit_id: UUID
    outcome_id: UUID
    confidence: float
    status: LinkStatus
    basis: str


@dataclass(frozen=True)
class GoalCoverage:
    """The boundary statement — what Padhanam can actually see (D171).

    An assess-not-replace platform reads only part of the user's world, so every
    read is valid only inside this boundary. ``has_coverage`` is the gate: with
    no goal linked to any ingested work, orphan/neglect verdicts are unproven and
    are suppressed in favour of the honest "uncovered" read.
    """

    goals_total: int
    goals_covered: int  # goals with >= 1 linked unit
    units_total: int
    units_linked: int  # units with >= 1 goal edge

    @property
    def has_coverage(self) -> bool:
        return self.goals_covered > 0


@dataclass(frozen=True)
class UncoveredGoal:
    """A goal with no linked evidence — *uncovered*, not neglected (D171).

    The honest read when Padhanam cannot see the work for a goal: a statement of
    its own blindness, never a judgment that the user has stopped.
    """

    outcome_id: UUID
    name: str
    reason: str


@dataclass(frozen=True)
class OrphanUnit:
    """A unit Padhanam could not link to a goal — recommendation-shaped (D169).

    Only emitted inside the coverage boundary (D171); outside it, an unlinked
    unit is unproven, not adrift.
    """

    unit_id: UUID
    title: str
    facet_count: int
    is_correlated: bool
    reason: str


@dataclass(frozen=True)
class GoalAssessment:
    """The coverage-honest moat reads (D169, D171).

    ``coverage`` is the boundary statement. ``uncovered_goals`` are goals with no
    linked evidence (honest, not a verdict). ``orphan_work`` is populated only
    when coverage exists — outside the boundary it is unproven and suppressed.
    Genuine *neglect* (a covered goal whose linked work has gone quiet) is a
    within-coverage signal reserved for a later session.
    """

    coverage: GoalCoverage
    uncovered_goals: tuple[UncoveredGoal, ...]
    orphan_work: tuple[OrphanUnit, ...]


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
    unit_tokens = {t for t in unit_title.split() if t not in _STOPWORDS}
    goal_tokens = {t for t in goal_name.split() if t not in _STOPWORDS}
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
            # Candidate tier: keyword match against the goal name or any of its
            # goal-owned alias terms (D174 tier two — "Fitness" → "Strength").
            match_targets = [normalise_title(goal.name)]
            match_targets.extend(
                normalise_title(a) for a in goal.aliases if normalise_title(a)
            )
            if any(
                _keyword_match(t, target)
                for t in titles
                for target in match_targets
            ):
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
    """Compute the coverage-honest moat reads (D169, D171).

    First the **coverage** boundary: how many goals are linked to ingested work,
    how many units are linked. A goal with no linked unit is **uncovered** —
    Padhanam cannot see its work, an honest statement of its own blindness, never
    a "you're neglecting this" verdict. **Orphan work is emitted only inside the
    coverage boundary** (``has_coverage``): with no goal linked to anything, an
    unlinked unit is unproven, so the orphan read is suppressed in favour of the
    coverage statement. Orphans, when emitted, are ordered cross-tool-first (the
    reverse-Kano restraint) then by title.
    """
    goal_ids = {goal.id for goal in goals}
    units_with_edge = {e.unit_id for e in edges}
    goals_with_edge = {e.outcome_id for e in edges} & goal_ids

    coverage = GoalCoverage(
        goals_total=len(goals),
        goals_covered=len(goals_with_edge),
        units_total=len(units),
        units_linked=len(units_with_edge),
    )

    uncovered = tuple(
        UncoveredGoal(
            outcome_id=goal.id,
            name=goal.name,
            reason=(
                f"No work is linked to “{goal.name}” yet — Padhanam can't see "
                "work for this goal. Not a sign you've stopped."
            ),
        )
        for goal in goals
        if goal.id not in goals_with_edge
    )

    orphan_work: tuple[OrphanUnit, ...] = ()
    if coverage.has_coverage:
        orphans = [
            OrphanUnit(
                unit_id=unit.unit_id,
                title=unit.title,
                facet_count=len(unit.facets),
                is_correlated=unit.is_correlated,
                reason=f"Padhanam couldn't link “{unit.title}” to a goal.",
            )
            for unit in units
            if unit.unit_id not in units_with_edge
        ]
        orphans.sort(key=lambda o: (0 if o.is_correlated else 1, o.title.lower()))
        orphan_work = tuple(orphans)

    return GoalAssessment(
        coverage=coverage,
        uncovered_goals=uncovered,
        orphan_work=orphan_work,
    )


__all__ = [
    "DEFAULT_GOAL_CONFIDENCE_FLOOR",
    "GoalAssessment",
    "GoalCoverage",
    "GoalEdge",
    "OrphanUnit",
    "UncoveredGoal",
    "assess_goals",
    "infer_goal_edges",
]
