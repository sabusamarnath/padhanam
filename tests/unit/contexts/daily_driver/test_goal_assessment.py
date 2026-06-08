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


def _facet_view(title, *, facet_type=FacetType.MEETING, present=True):
    return UnitFacetView(
        facet_type=facet_type,
        facet_id=uuid4(),
        title=title,
        occurred_at=None,
        status=LinkStatus.CONFIRMED,
        confidence=1.0,
        basis="anchor",
        present=present,
    )


def _unit(title, *, facets=None, unit_id=None):
    fs = facets or (_facet_view(title),)
    return UnitView(
        unit_id=unit_id or uuid4(),
        title=title,
        facets=tuple(fs),
    )


def _progressive_goal(name, *, lever_commitment_id, goal_id=None):
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
