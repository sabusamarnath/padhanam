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

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from uuid import UUID

from contexts.daily_driver.domain.calendar_domain import resolve_calendar_domain
from contexts.daily_driver.domain.goal import Goal
from contexts.daily_driver.domain.unit_view import UnitView
from contexts.daily_driver.domain.work_unit import (
    FacetType,
    LinkStatus,
    normalise_title,
)

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
class LinkedGoal:
    """A covered goal's linked work, folded by source series (D175 reaching the
    coverage read; D177's dense activation case).

    A goal whose work is one recurring routine — or several, the health
    regimen's four medications — links one unit per instance (~120 each, ~480
    total). The coverage read must show the **distinct routines** (~4), not the
    raw serving instances (~480), or a dense goal floods exactly as the orphan
    read did before D175. ``distinct_units`` folds linked units sharing a source
    series into one (the same fold the orphan read uses); ``total_instances`` is
    the raw count; ``confirmed_distinct`` is how many of the distinct routines
    carry a confirmed (0.9) edge.
    """

    outcome_id: UUID
    name: str
    distinct_units: int
    total_instances: int
    confirmed_distinct: int


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
    # Recurrence grouping (D175): a recurring series renders as one orphan row
    # carrying its instance count, not N raw instances. ``series_id`` is the
    # source-series id (``None`` for a one-off); ``instance_count`` is the number
    # of unlinked instances folded into this row (1 for a one-off).
    series_id: str | None = None
    instance_count: int = 1


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
    linked_goals: tuple[LinkedGoal, ...] = ()


# ----------------------------------------------------------- D180 grouped read
# The moat view anchored on the goal served: units grouped under the :Outcome
# they SERVE, orphans under one unlinked group. A read-and-render projection
# over the same inputs the coverage read takes (units, goals, SERVES edges) —
# no graph write. The D175 series-fold applies before grouping (a recurring
# unit is one row carrying its instance count).


@dataclass(frozen=True)
class GroupedUnit:
    """One folded unit row inside a group (D180; the D175 fold applied).

    ``confirmed`` is whether any serving edge for this row is confirmed (0.9,
    D169) versus candidate-only; ``False`` for an unlinked (orphan) row.
    ``instance_count`` is how many instances of a recurring series this row
    folds (1 for a one-off). ``occurred_at`` is the row's representative time
    (the earliest present facet), used for within-group ordering.
    """

    unit_id: UUID
    title: str
    facet_count: int
    is_correlated: bool
    confirmed: bool
    # The unit's present facet types (task / meeting / email), ordered, deduped
    # — the row's category channel (design-language §2: category in icon).
    facet_types: tuple[str, ...] = ()
    series_id: str | None = None
    instance_count: int = 1
    occurred_at: datetime | None = None


@dataclass(frozen=True)
class GoalGroup:
    """A goal gathering the units that SERVE it (D180).

    ``email_activity`` (D183/S89) is the job-search email activity folded to a
    **count by kind** — emails are seriesless, so the D175 series-fold can't
    collapse them; a count is the right shape (not a row per email). The folded
    email units do **not** appear in ``units``. ``active`` is whether that
    activity is **recent** (within the recency window) — a goal reads active on
    recent work, never on the mere presence of old units.
    """

    outcome_id: UUID
    name: str
    domain: str | None
    units: tuple[GroupedUnit, ...]
    email_activity: tuple[tuple[str, int], ...] = ()
    active: bool = False


@dataclass(frozen=True)
class GoalGroupedUnits:
    """The moat view anchored on the goal served (D180).

    ``groups`` are the covered goals each gathering their (folded) serving unit
    rows, in the goals' canonical order. ``unlinked`` is the single group of
    orphan units (no SERVES edge), populated only inside the coverage boundary
    (D171) and folded the same way. ``coverage`` is the boundary statement.
    """

    groups: tuple[GoalGroup, ...]
    unlinked: tuple[GroupedUnit, ...]
    coverage: GoalCoverage


def _unit_time(unit: UnitView) -> datetime | None:
    """A unit's representative time: the earliest present facet's ``occurred_at``."""
    times = [
        f.occurred_at
        for f in unit.facets
        if f.present and f.occurred_at is not None
    ]
    return min(times) if times else None


_FACET_PRIORITY = {"task": 0, "meeting": 1, "email": 2}


def _unit_facet_types(unit: UnitView) -> tuple[str, ...]:
    """The unit's present facet types, deduped and priority-ordered (the row's
    category channel — task / meeting / email)."""
    seen: list[str] = []
    for f in unit.facets:
        if f.present and f.facet_type.value not in seen:
            seen.append(f.facet_type.value)
    seen.sort(key=lambda t: _FACET_PRIORITY.get(t, 9))
    return tuple(seen)


def _fold_units_to_rows(
    items: list[tuple[UnitView, bool]]
) -> tuple[GroupedUnit, ...]:
    """Fold (unit, confirmed) pairs by source series (D175) into one row each.

    Units sharing a recurring-series id collapse to one representative row
    carrying the instance count; a series is ``confirmed`` if any of its
    members' serving edges is confirmed. Rows order by time then title (the
    moat has no per-day proposed order — that is the action Today's, D180).
    """
    by_series: dict[object, list[tuple[UnitView, bool]]] = {}
    order: list[object] = []
    for unit, confirmed in items:
        key: object = unit.series_id or ("solo", unit.unit_id)
        if key not in by_series:
            by_series[key] = []
            order.append(key)
        by_series[key].append((unit, confirmed))
    rows: list[GroupedUnit] = []
    for key in order:
        members = by_series[key]
        rep = members[0][0]
        rows.append(
            GroupedUnit(
                unit_id=rep.unit_id,
                title=rep.title,
                facet_count=len(rep.facets),
                is_correlated=rep.is_correlated,
                confirmed=any(c for _, c in members),
                facet_types=_unit_facet_types(rep),
                series_id=rep.series_id,
                instance_count=len(members),
                occurred_at=_unit_time(rep),
            )
        )
    rows.sort(
        key=lambda r: (
            r.occurred_at is None,
            r.occurred_at.timestamp() if r.occurred_at is not None else 0.0,
            r.title.lower(),
        )
    )
    return tuple(rows)


# D183/S89: a goal reads active on email activity no older than this.
_EMAIL_ACTIVE_RECENCY_DAYS = 30


def _email_facet_kind(
    unit: UnitView, email_kinds: dict[UUID, str]
) -> str | None:
    """The job-search kind of the unit's confirmed email facet, if any."""
    for f in unit.facets:
        if f.facet_type is FacetType.EMAIL and f.present and f.facet_id in email_kinds:
            return email_kinds[f.facet_id]
    return None


def group_units_by_goal(
    units: tuple[UnitView, ...],
    goals: tuple[Goal, ...],
    edges: tuple[GoalEdge, ...],
    email_kinds: dict[UUID, str] | None = None,
    now: datetime | None = None,
) -> GoalGroupedUnits:
    """Group units under the goal each SERVES; orphans under one unlinked group.

    Pure projection (D180) over the coverage read's inputs — no graph write. A
    unit serving multiple goals appears under each. Groups follow the goals'
    given (canonical) order; the unlinked group is rendered last and is emitted
    only inside the coverage boundary (D171). The D175 fold runs before grouping.

    ``email_kinds`` (D183/S89) maps a confirmed job-search email's facet_id to
    its kind: a goal's units carrying such facets fold to a **count by kind**
    (``email_activity``), not a row per email (emails are seriesless), and the
    goal reads ``active`` when that activity is **recent** (within the recency
    window of ``now``). Without it, behaviour is unchanged.
    """
    email_kinds = email_kinds or {}
    goal_ids = {g.id for g in goals}
    units_with_edge = {e.unit_id for e in edges}
    goals_with_edge = {e.outcome_id for e in edges} & goal_ids
    coverage = GoalCoverage(
        goals_total=len(goals),
        goals_covered=len(goals_with_edge),
        units_total=len(units),
        units_linked=len(units_with_edge),
    )
    units_by_id = {u.unit_id: u for u in units}
    edges_by_goal: dict[UUID, list[GoalEdge]] = {}
    for e in edges:
        edges_by_goal.setdefault(e.outcome_id, []).append(e)
    recency_cut = (
        now.timestamp() - _EMAIL_ACTIVE_RECENCY_DAYS * 86400
        if now is not None
        else None
    )

    groups: list[GoalGroup] = []
    for goal in goals:
        g_edges = edges_by_goal.get(goal.id)
        if not g_edges:
            continue
        items: list[tuple[UnitView, bool]] = []
        kind_counts: Counter[str] = Counter()
        active = False
        for e in g_edges:
            unit = units_by_id.get(e.unit_id)
            if unit is None:
                continue
            kind = _email_facet_kind(unit, email_kinds)
            if kind is not None:
                # Seriesless job-search email: fold to a count by kind, not a row.
                kind_counts[kind] += 1
                t = _unit_time(unit)
                if recency_cut is not None and t is not None and t.timestamp() >= recency_cut:
                    active = True
                continue
            items.append((unit, e.status is LinkStatus.CONFIRMED))
        groups.append(
            GoalGroup(
                outcome_id=goal.id,
                name=goal.name,
                domain=goal.domain,
                units=_fold_units_to_rows(items),
                email_activity=tuple(sorted(kind_counts.items())),
                active=active,
            )
        )

    unlinked: tuple[GroupedUnit, ...] = ()
    if coverage.has_coverage:
        orphans = [
            (u, False) for u in units if u.unit_id not in units_with_edge
        ]
        unlinked = _fold_units_to_rows(orphans)

    return GoalGroupedUnits(
        groups=tuple(groups), unlinked=unlinked, coverage=coverage
    )


def _goal_commitment_ids(goal: Goal) -> tuple[UUID, ...]:
    """Every Postgres commitment id that serves as a lever for the goal.

    A goal may carry many lever-commitments (D177): the primary
    ``lever_commitment_id``, the full ``lever_commitment_ids`` set (any mode),
    and a sequence's ``steps``. The confirmed tier matches a unit against any of
    them. Deduplicated, order-preserving.
    """
    ids: list[UUID] = []
    seen: set[UUID] = set()
    candidates = (
        goal.lever_commitment_id,
        *goal.lever_commitment_ids,
        *(step.commitment_id for step in goal.steps),
    )
    for cid in candidates:
        if cid is not None and cid not in seen:
            seen.add(cid)
            ids.append(cid)
    return tuple(ids)


def commitment_domains_from_goals(goals: Iterable[Goal]) -> dict[UUID, str]:
    """Map each goal's lever-commitment ids to that goal's domain (D179).

    A Commitment that levers a goal takes the goal's domain on the Today
    surface (the direct lever link — no SERVES-unit join). A commitment that
    levers no goal, or whose goal carries no explicit domain, is absent from
    the map and keeps the surface's work default. The value is clamped to the
    known domain set (``resolve_calendar_domain``) so an unknown value never
    reaches the surface. Cross-goal commitment sharing is out (D177); on the
    rare overlap the last goal wins, deterministically by the goals' order.
    """
    out: dict[UUID, str] = {}
    for goal in goals:
        if goal.domain is None:
            continue
        domain = resolve_calendar_domain(goal.domain)
        for cid in _goal_commitment_ids(goal):
            out[cid] = domain
    return out


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


# --- D183/S89: the classifier-fed edge -------------------------------------
# A rule classifier's verdict, not a lever-title match, establishes the edge —
# a distinct, higher-specificity basis. Confidence sits at/above CONFIRMED.
_EMAIL_RULE_CONFIDENCE = 0.95
_EMAIL_RULE_BASIS = "email-job-search"
# Tiebreak when a unit-goal pair is reached by more than one path: the
# rule-confirmed basis wins (higher specificity), then commitment, then
# goal-name (the D183 dedup requirement).
_BASIS_PRIORITY = {_EMAIL_RULE_BASIS: 0, "commitment": 1, "goal-name": 2}


def infer_email_job_search_edges(
    units: tuple[UnitView, ...],
    outcome_id: UUID,
    confirmed_facet_ids: frozenset[UUID],
) -> tuple[GoalEdge, ...]:
    """A CONFIRMED SERVES edge to ``outcome_id`` (Get a job) for each unit
    carrying a present EMAIL facet the rules confirmed as job-search (D183/S89).

    The verdict is the classifier's, persisted on the store and read back each
    correlate run (so the edges are durable), not a lever-title match — hence
    the distinct ``email-job-search`` basis at high confidence. One edge per
    unit; the caller dedups against the title-match edges (``dedup_goal_edges``).
    """
    edges: list[GoalEdge] = []
    seen: set[UUID] = set()
    for unit in units:
        if unit.unit_id in seen:
            continue
        if any(
            f.facet_type is FacetType.EMAIL
            and f.present
            and f.facet_id in confirmed_facet_ids
            for f in unit.facets
        ):
            edges.append(
                GoalEdge(
                    unit_id=unit.unit_id,
                    outcome_id=outcome_id,
                    confidence=_EMAIL_RULE_CONFIDENCE,
                    status=LinkStatus.CONFIRMED,
                    basis=_EMAIL_RULE_BASIS,
                )
            )
            seen.add(unit.unit_id)
    return tuple(edges)


def dedup_goal_edges(edges: tuple[GoalEdge, ...]) -> tuple[GoalEdge, ...]:
    """One edge per ``(unit_id, outcome_id)``; on collision keep the
    higher-specificity basis (email-job-search > commitment > goal-name, D183).
    Order-preserving on first appearance of each kept key."""
    best: dict[tuple[UUID, UUID], GoalEdge] = {}
    order: list[tuple[UUID, UUID]] = []
    for e in edges:
        key = (e.unit_id, e.outcome_id)
        cur = best.get(key)
        if cur is None:
            best[key] = e
            order.append(key)
        elif _BASIS_PRIORITY.get(e.basis, 9) < _BASIS_PRIORITY.get(cur.basis, 9):
            best[key] = e
    return tuple(best[k] for k in order)


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


def _group_orphans_by_series(units: list[UnitView]) -> tuple[OrphanUnit, ...]:
    """Fold orphan units sharing a source series into one row (D175).

    Recurring instances carry the same ``series_id`` (the calendar
    ``recurringEventId``); they collapse to a single orphan row with an
    ``instance_count``, so the read shows the distinct items (~40), not the raw
    instances (~982). A unit with no series id (a one-off, a task, an email) is
    its own row (count 1). The data model is untouched — this folds the *read*
    only. Representative ordering is correlated-first, then title.
    """
    groups: dict[object, list[UnitView]] = {}
    order: list[object] = []
    for unit in units:
        # None-series units never merge — key each on its own unit id.
        key: object = unit.series_id or ("solo", unit.unit_id)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(unit)

    rows: list[OrphanUnit] = []
    for key in order:
        members = groups[key]
        rep = members[0]
        count = len(members)
        reason = (
            f"Padhanam couldn't link “{rep.title}” "
            f"(×{count} recurring instances) to a goal."
            if count > 1
            else f"Padhanam couldn't link “{rep.title}” to a goal."
        )
        rows.append(
            OrphanUnit(
                unit_id=rep.unit_id,
                title=rep.title,
                facet_count=len(rep.facets),
                is_correlated=rep.is_correlated,
                reason=reason,
                series_id=rep.series_id,
                instance_count=count,
            )
        )
    rows.sort(key=lambda o: (0 if o.is_correlated else 1, o.title.lower()))
    return tuple(rows)


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
        unlinked = [u for u in units if u.unit_id not in units_with_edge]
        orphan_work = _group_orphans_by_series(unlinked)

    # Per-goal coverage, folded by source series (D175 reaching coverage; D177).
    # A dense goal (the health regimen's four medications, ~120 instances each)
    # reads as its distinct routines, not the raw serving instances — the same
    # fold the orphan read uses, so the coverage read does not flood.
    units_by_id = {u.unit_id: u for u in units}
    edges_by_goal: dict[UUID, list[GoalEdge]] = {}
    for e in edges:
        edges_by_goal.setdefault(e.outcome_id, []).append(e)
    linked_goals: list[LinkedGoal] = []
    for goal in goals:
        g_edges = edges_by_goal.get(goal.id)
        if not g_edges:
            continue
        series_count: dict[object, int] = {}
        series_confirmed: dict[object, bool] = {}
        for e in g_edges:
            unit = units_by_id.get(e.unit_id)
            if unit is None:
                continue
            key = unit.series_id or ("solo", unit.unit_id)
            series_count[key] = series_count.get(key, 0) + 1
            if e.status is LinkStatus.CONFIRMED:
                series_confirmed[key] = True
        linked_goals.append(
            LinkedGoal(
                outcome_id=goal.id,
                name=goal.name,
                distinct_units=len(series_count),
                total_instances=sum(series_count.values()),
                confirmed_distinct=sum(
                    1 for k in series_count if series_confirmed.get(k)
                ),
            )
        )

    return GoalAssessment(
        coverage=coverage,
        uncovered_goals=uncovered,
        orphan_work=orphan_work,
        linked_goals=tuple(linked_goals),
    )


__all__ = [
    "DEFAULT_GOAL_CONFIDENCE_FLOOR",
    "GoalAssessment",
    "GoalCoverage",
    "GoalEdge",
    "LinkedGoal",
    "OrphanUnit",
    "GoalGroup",
    "GoalGroupedUnits",
    "GroupedUnit",
    "UncoveredGoal",
    "assess_goals",
    "commitment_domains_from_goals",
    "dedup_goal_edges",
    "group_units_by_goal",
    "infer_email_job_search_edges",
    "infer_goal_edges",
]
