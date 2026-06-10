"""Unit tests for the goal-aligned assessment domain (S67, D169, D166)."""

from __future__ import annotations

from uuid import UUID, uuid4

from contexts.daily_driver.domain.goal import (
    ControlAxis,
    Goal,
    GoalMode,
    LevelLadder,
    Subject,
)
from contexts.daily_driver.domain.goal_assessment import (
    assess_goals,
    infer_goal_edges,
)
from contexts.daily_driver.domain.unit_view import UnitFacetView, UnitView
from contexts.daily_driver.domain.work_unit import FacetType, LinkStatus

_TENANT = UUID("00000000-0000-4000-8000-00000000d001")


def _facet_view(title, *, facet_type=FacetType.MEETING, present=True, series_id=None):
    return UnitFacetView(
        facet_type=facet_type,
        facet_id=uuid4(),
        title=title,
        occurred_at=None,
        status=LinkStatus.CONFIRMED,
        confidence=1.0,
        basis="anchor",
        present=present,
        series_id=series_id,
    )


def _unit(title, *, facets=None, unit_id=None, series_id=None):
    fs = facets or (_facet_view(title, series_id=series_id),)
    return UnitView(
        unit_id=unit_id or uuid4(),
        title=title,
        facets=tuple(fs),
    )


def _progressive_goal(name, *, lever_commitment_id, goal_id=None, aliases=()):
    return Goal(
        id=goal_id or uuid4(),
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        name=name,
        mode=GoalMode.PROGRESSIVE,
        control=ControlAxis.SELF,
        subject=Subject.SELF,
        lever_commitment_id=lever_commitment_id,
        ladder=LevelLadder(levels=("A1", "A2", "B1"), current_target_level="A2"),
        aliases=tuple(aliases),
    )


def test_confirmed_edge_when_facet_matches_a_lever_commitment_name():
    cid = uuid4()
    goal = _progressive_goal("German", lever_commitment_id=cid)
    unit = _unit("German practice", facets=(_facet_view("German practice"),))
    edges = infer_goal_edges(
        (unit,), (goal,), {cid: "German practice"}
    )
    assert len(edges) == 1
    assert edges[0].status is LinkStatus.CONFIRMED
    assert edges[0].basis == "commitment"
    assert edges[0].outcome_id == goal.id


def test_candidate_edge_when_facet_keyword_matches_the_goal_name():
    cid = uuid4()
    goal = _progressive_goal("German", lever_commitment_id=cid)
    # No commitment-name match, but the facet title contains the goal name.
    unit = _unit("German conversation with tutor")
    edges = infer_goal_edges((unit,), (goal,), {cid: "Daily drills"})
    assert len(edges) == 1
    assert edges[0].status is LinkStatus.CANDIDATE
    assert edges[0].basis == "goal-name"


def test_short_high_signal_word_links_under_the_stopword_filter():
    # D172: "job" is three chars (below the old length guard) but high-signal,
    # so it links "Get a job" to a "Job search" unit via the shared token.
    cid = uuid4()
    goal = _progressive_goal("Get a job", lever_commitment_id=cid)
    unit = _unit("Job search")
    edges = infer_goal_edges((unit,), (goal,), {cid: "Apply to roles"})
    assert len(edges) == 1
    assert edges[0].status is LinkStatus.CANDIDATE
    assert edges[0].basis == "goal-name"


def test_a_stopword_only_overlap_forms_no_edge():
    # The unit and goal share only the stopword "get" — no high-signal token
    # in common, so the stopword filter forms no candidate edge.
    cid = uuid4()
    goal = _progressive_goal("Get a job", lever_commitment_id=cid)
    unit = _unit("Get a coffee")
    edges = infer_goal_edges((unit,), (goal,), {cid: "Apply to roles"})
    assert edges == ()


def test_alias_term_links_a_unit_with_no_name_overlap():
    # D174 tier two: "Fitness" shares no characters with "Strength", but links
    # via the goal-owned alias "fitness" at candidate tier.
    cid = uuid4()
    goal = _progressive_goal(
        "Strength", lever_commitment_id=cid, aliases=("fitness", "gym")
    )
    unit = _unit("Fitness")
    edges = infer_goal_edges((unit,), (goal,), {cid: "Strength micro-sessions"})
    assert len(edges) == 1
    assert edges[0].status is LinkStatus.CANDIDATE
    assert edges[0].basis == "goal-name"
    assert edges[0].outcome_id == goal.id


def test_confirmed_takes_precedence_over_candidate_for_a_goal():
    cid = uuid4()
    goal = _progressive_goal("German", lever_commitment_id=cid)
    # Facet matches both the commitment name and the goal name; only the
    # confirmed edge is emitted (one edge per unit-goal pair).
    unit = _unit("German practice")
    edges = infer_goal_edges((unit,), (goal,), {cid: "German practice"})
    assert len(edges) == 1
    assert edges[0].status is LinkStatus.CONFIRMED


def test_no_edge_when_neither_tier_matches():
    cid = uuid4()
    goal = _progressive_goal("German", lever_commitment_id=cid)
    unit = _unit("Quarterly budget review")
    edges = infer_goal_edges((unit,), (goal,), {cid: "Daily drills"})
    assert edges == ()


def test_orphan_work_is_a_unit_with_no_edge_confirmed_or_candidate():
    cid = uuid4()
    goal = _progressive_goal("German", lever_commitment_id=cid)
    served = _unit("German practice")
    orphan = _unit("Quarterly budget review")
    units = (served, orphan)
    edges = infer_goal_edges(units, (goal,), {cid: "German practice"})
    assessment = assess_goals(units, (goal,), edges)
    orphan_ids = {o.unit_id for o in assessment.orphan_work}
    assert orphan.unit_id in orphan_ids
    assert served.unit_id not in orphan_ids


def test_a_candidate_edge_is_enough_to_keep_a_unit_off_the_orphan_list():
    cid = uuid4()
    goal = _progressive_goal("German", lever_commitment_id=cid)
    # Candidate-only link (goal-name match, not commitment) — still not orphan.
    unit = _unit("German listening")
    edges = infer_goal_edges((unit,), (goal,), {cid: "Daily drills"})
    assert edges[0].status is LinkStatus.CANDIDATE
    assessment = assess_goals((unit,), (goal,), edges)
    assert assessment.orphan_work == ()


def test_a_goal_with_no_link_reads_uncovered_not_neglected():
    # D171: an unlinked goal is uncovered (Padhanam can't see its work), never
    # neglected. The served goal establishes coverage so the read is valid.
    cid_served, cid_unseen = uuid4(), uuid4()
    served_goal = _progressive_goal("German", lever_commitment_id=cid_served)
    unseen_goal = _progressive_goal("Marathon", lever_commitment_id=cid_unseen)
    unit = _unit("German practice")
    goals = (served_goal, unseen_goal)
    edges = infer_goal_edges(
        (unit,), goals, {cid_served: "German practice", cid_unseen: "Long run"}
    )
    assessment = assess_goals((unit,), goals, edges)
    uncovered_ids = {g.outcome_id for g in assessment.uncovered_goals}
    assert unseen_goal.id in uncovered_ids
    assert served_goal.id not in uncovered_ids
    assert assessment.coverage.goals_covered == 1
    assert assessment.coverage.goals_total == 2


def test_no_coverage_suppresses_orphan_and_reports_uncovered():
    # The trust fix (D171): with nothing linked, the platform must not emit
    # orphan/neglect verdicts — it reports its own blindness instead.
    cid = uuid4()
    goal = _progressive_goal("German", lever_commitment_id=cid)
    # No unit matches the goal/lever → 0 edges → no coverage.
    units = (_unit("Quarterly budget review"), _unit("Call the bank"))
    edges = infer_goal_edges(units, (goal,), {cid: "German practice"})
    assert edges == ()
    assessment = assess_goals(units, (goal,), edges)
    assert assessment.coverage.has_coverage is False
    assert assessment.coverage.goals_covered == 0
    assert assessment.coverage.units_linked == 0
    # Orphan verdicts are unproven outside coverage → suppressed.
    assert assessment.orphan_work == ()
    # The goal is reported uncovered, honestly.
    assert {g.outcome_id for g in assessment.uncovered_goals} == {goal.id}


def test_orphans_emitted_and_ordered_cross_tool_first_when_coverage_exists():
    cid = uuid4()
    goal = _progressive_goal("German", lever_commitment_id=cid)
    served = _unit("German practice")  # establishes coverage
    solo = _unit("Zeta solo errand")
    cross = _unit(
        "Alpha cross-tool work",
        facets=(
            _facet_view("Alpha cross-tool work", facet_type=FacetType.TASK),
            _facet_view("Alpha cross-tool work", facet_type=FacetType.MEETING),
        ),
    )
    units = (served, solo, cross)
    edges = infer_goal_edges(units, (goal,), {cid: "German practice"})
    assessment = assess_goals(units, (goal,), edges)
    assert assessment.coverage.has_coverage is True
    # The cross-tool orphan leads; the served unit is not orphan.
    assert assessment.orphan_work[0].unit_id == cross.unit_id
    assert assessment.orphan_work[0].is_correlated
    assert served.unit_id not in {o.unit_id for o in assessment.orphan_work}


def test_orphan_recurring_instances_fold_to_one_row_by_series():
    # D175: coverage exists (one linked unit), so orphan_work is emitted (D171);
    # three instances of one recurring series collapse to a single orphan row.
    cid = uuid4()
    goal = _progressive_goal("German", lever_commitment_id=cid)
    linked = _unit("German practice")
    series = "recurring-event-abc"
    orphans = tuple(
        _unit("Medication reminder", series_id=series) for _ in range(3)
    )
    units = (linked, *orphans)
    edges = infer_goal_edges(units, (goal,), {cid: "German practice"})
    assessment = assess_goals(units, (goal,), edges)
    folded = [o for o in assessment.orphan_work if o.series_id == series]
    assert len(folded) == 1
    assert folded[0].instance_count == 3
    assert "×3 recurring instances" in folded[0].reason
    # The data model is untouched: the three instances are still three units in.
    assert len(units) == 4


def test_orphans_without_a_series_stay_separate_rows():
    # D175: one-offs (no series id) never merge — each is its own row, count 1.
    cid = uuid4()
    goal = _progressive_goal("German", lever_commitment_id=cid)
    linked = _unit("German practice")
    units = (linked, _unit("Haircut"), _unit("Call Natwest"))
    edges = infer_goal_edges(units, (goal,), {cid: "German practice"})
    assessment = assess_goals(units, (goal,), edges)
    solo = [o for o in assessment.orphan_work if o.series_id is None]
    assert len(solo) == 2
    assert all(o.instance_count == 1 for o in solo)


def test_removed_facets_do_not_drive_a_match():
    cid = uuid4()
    goal = _progressive_goal("German", lever_commitment_id=cid)
    # The only facet that would match is gone from its cache (present=False).
    unit = _unit(
        "German practice",
        facets=(_facet_view("German practice", present=False),),
    )
    edges = infer_goal_edges((unit,), (goal,), {cid: "German practice"})
    assert edges == ()


def test_multi_commitment_goal_confirms_against_any_lever():
    """D177: a goal carrying a lever-commitment per work-type confirms a unit
    against ANY of its commitments (the health regimen's four medication
    routines), not just the first lever (the S69 single-lever cap), and a
    non-matching title produces no false confirmed edge."""
    c1, c2, c3, c4 = uuid4(), uuid4(), uuid4(), uuid4()
    goal = Goal(
        id=uuid4(),
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        name="Health regimen",
        mode=GoalMode.HOMEOSTATIC,
        control=ControlAxis.SELF,
        subject=Subject.SELF,
        lever_commitment_ids=(c1, c2, c3, c4),
    )
    names = {c1: "med one", c2: "med two", c3: "med three", c4: "med four"}
    u1, u2, u3, u4 = (
        _unit("med one"),
        _unit("med two"),
        _unit("med three"),
        _unit("med four"),
    )
    noise = _unit("buy groceries")
    edges = infer_goal_edges((u1, u2, u3, u4, noise), (goal,), names)
    confirmed = {e.unit_id for e in edges if e.basis == "commitment"}
    # All four work-types confirm — not just the first lever.
    assert confirmed == {u1.unit_id, u2.unit_id, u3.unit_id, u4.unit_id}
    assert all(e.confidence == 0.9 for e in edges if e.basis == "commitment")
    # The unrelated unit confirms against none of the four (no false positive).
    assert noise.unit_id not in confirmed


def test_dense_recurring_coverage_folds_in_the_coverage_read():
    """D175's recurrence-fold reaches the coverage read (D177): a goal whose
    linked work is one recurring series of N instances reads as 1 distinct
    routine carrying N instances, not N raw linked units — so a dense goal
    (the health regimen's medications, ~120 instances each) does not flood."""
    cid = uuid4()
    goal = _progressive_goal("Medication", lever_commitment_id=cid)
    series = "recurring-med-series"
    units = tuple(
        _unit("daily med", series_id=series, unit_id=uuid4()) for _ in range(120)
    )
    edges = infer_goal_edges(units, (goal,), {cid: "daily med"})
    assessment = assess_goals(units, (goal,), edges)
    linked = {lg.outcome_id: lg for lg in assessment.linked_goals}[goal.id]
    assert linked.distinct_units == 1  # one routine, folded
    assert linked.total_instances == 120  # the raw instance count, not flooded
    assert linked.confirmed_distinct == 1
