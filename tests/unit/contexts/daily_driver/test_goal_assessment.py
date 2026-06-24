"""Unit tests for the goal-aligned assessment domain (S67, D169, D166)."""

from __future__ import annotations

from uuid import UUID, uuid4

from contexts.daily_driver.domain.goal import (
    ControlAxis,
    Goal,
    GoalMode,
    LevelLadder,
    LeverStep,
    StepState,
    Subject,
    Terminal,
    TerminalState,
)
from datetime import datetime, timedelta, timezone

from dataclasses import fields

from contexts.daily_driver.domain.goal_assessment import (
    NO_CLEAR_BASIS,
    GoalEdge,
    GoalGroup,
    GroupedUnit,
    _keyword_match,
    assess_goals,
    binding_rationale,
    commitment_domains_from_goals,
    group_units_by_goal,
    infer_goal_edges,
    shared_significant_tokens,
    significant_tokens,
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


# --- S103d/D204: match rule == read-side basis rule (shared token, no substring)


def _keyword_has_basis(unit_title: str, target: str) -> bool:
    """The read-side verdict for a keyword binding of ``unit_title`` to ``target``:
    True when ``binding_rationale`` finds a basis, False when it reads
    NO_CLEAR_BASIS. The mirror of the matcher's ``_keyword_match`` it must equal."""
    term, _ = binding_rationale(
        unit_title=unit_title,
        element_label=target,
        tier="lexical_keyword",
        token_element_counts={},
    )
    return term != NO_CLEAR_BASIS


def _alias_has_basis(unit_title: str, target: str) -> bool:
    """The read-side verdict for an alias binding: the alias tier reads the
    unit∩goal-name(/alias) overlap, so it has a basis iff a significant token is
    shared — the same predicate ``_keyword_match`` applies in the alias tier."""
    term, _ = binding_rationale(
        unit_title=unit_title,
        element_label="",
        tier="alias",
        token_element_counts={},
        goal_tokens=significant_tokens(target),
    )
    return term != NO_CLEAR_BASIS


# Pairs spanning the three cases: shared significant token, substring-only (the
# behaviour S103d removes), and disjoint. "prunes" contains the substring "run";
# "jobsworth" contains "job" — the substring-only fragments the old rule bound.
_TIE_PAIRS = (
    ("apply to roles", "apply to roles"),          # exact overlap
    ("drafted application for acme", "application response rate"),  # shared token
    ("morning run by the river", "run"),           # shared token "run"
    ("buy prunes", "run"),                          # substring-only: prunes ⊃ run
    ("jobsworth attitude", "job"),                  # substring-only: jobsworth ⊃ job
    ("dentist appointment", "marathon"),            # disjoint
)


def test_match_rule_ties_to_the_read_side_basis_rule():
    # The divergence guard (D204): the matcher binds a (unit, target) pair iff the
    # read-side finds a basis for it — for BOTH the keyword and alias tiers. A
    # future edit that re-introduced substring into one rule but not the other
    # would break a substring-only pair here.
    for unit_title, target in _TIE_PAIRS:
        binds = _keyword_match(unit_title, target)
        assert binds == _keyword_has_basis(unit_title, target), (unit_title, target)
        assert binds == _alias_has_basis(unit_title, target), (unit_title, target)


def test_substring_without_shared_token_does_not_bind():
    # Precision (D204): "prunes" contains the substring "run", but they share no
    # significant token — the old rule bound it, the new rule does not.
    assert "run" in "buy prunes"  # the substring the old branch fired on
    assert _keyword_match("buy prunes", "run") is False
    assert _keyword_match("jobsworth attitude", "job") is False


def test_shared_significant_token_still_binds():
    # Recall (D204): a genuine shared token still binds, both directions.
    assert _keyword_match("morning run by the river", "run") is True
    assert _keyword_match("Get a job", "Job search") is True
    assert shared_significant_tokens("Job search", "Get a job") == frozenset({"job"})


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


# --- D179: commitment_domains_from_goals (a commitment takes its goal's domain)

def _domain_goal(
    *, name, domain, mode=GoalMode.HOMEOSTATIC,
    lever_commitment_id=None, lever_commitment_ids=(), steps=(),
):
    # A sequence goal requires a terminal; supply one when testing steps.
    terminal = (
        Terminal(target="Offer accepted", state=TerminalState.PENDING)
        if mode is GoalMode.SEQUENCE
        else None
    )
    return Goal(
        id=uuid4(),
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        name=name,
        mode=mode,
        control=ControlAxis.SELF,
        subject=Subject.SELF,
        lever_commitment_id=lever_commitment_id,
        lever_commitment_ids=tuple(lever_commitment_ids),
        steps=tuple(steps),
        terminal=terminal,
        domain=domain,
    )


def test_commitment_domains_maps_primary_lever_to_goal_domain():
    cid = uuid4()
    goal = _domain_goal(
        name="Wide World Marathon", domain="personal", lever_commitment_id=cid
    )
    assert commitment_domains_from_goals([goal]) == {cid: "personal"}


def test_commitment_domains_covers_all_lever_commitments():
    # A regimen with several lever-commitments (D177) — all take the one domain.
    a, b, c = uuid4(), uuid4(), uuid4()
    goal = _domain_goal(
        name="Regimen", domain="personal",
        lever_commitment_id=a, lever_commitment_ids=(a, b, c),
    )
    assert commitment_domains_from_goals([goal]) == {
        a: "personal", b: "personal", c: "personal"
    }


def test_commitment_domains_covers_sequence_steps():
    s1, s2 = uuid4(), uuid4()
    goal = _domain_goal(
        name="Get a job", domain="work", mode=GoalMode.SEQUENCE,
        steps=(
            LeverStep(commitment_id=s1, order=1, state=StepState.READY),
            LeverStep(commitment_id=s2, order=2, state=StepState.BLOCKED),
        ),
    )
    # A work goal's levers resolve to work (the fix is per-goal, not blanket).
    assert commitment_domains_from_goals([goal]) == {s1: "work", s2: "work"}


def test_commitment_domains_skips_goal_without_explicit_domain():
    cid = uuid4()
    goal = _domain_goal(name="Unset", domain=None, lever_commitment_id=cid)
    assert commitment_domains_from_goals([goal]) == {}


def test_commitment_domains_clamps_unknown_domain_to_work():
    # "health" is not a known surface domain (the distinct tier is S83-deferred),
    # so it clamps to the surface default rather than rendering an unknown tier.
    cid = uuid4()
    goal = _domain_goal(name="Meds", domain="health", lever_commitment_id=cid)
    assert commitment_domains_from_goals([goal]) == {cid: "work"}


# --- D180: group_units_by_goal (the moat view anchored on the goal served) ---

def _served_unit(title, *, series_id=None, occurred_at=None,
                 facet_type=FacetType.MEETING):
    return UnitView(
        unit_id=uuid4(),
        title=title,
        facets=(
            UnitFacetView(
                facet_type=facet_type, facet_id=uuid4(), title=title,
                occurred_at=occurred_at, status=LinkStatus.CONFIRMED,
                confidence=1.0, basis="anchor", present=True,
                series_id=series_id,
            ),
        ),
    )


def _edge(unit, goal, status=LinkStatus.CONFIRMED, basis="commitment"):
    return GoalEdge(
        unit_id=unit.unit_id, outcome_id=goal.id, confidence=0.9,
        status=status, basis=basis,
    )


def test_group_yields_one_group_of_n_not_n_flat_rows():
    goal = _progressive_goal("German", lever_commitment_id=uuid4())
    units = (_served_unit("A"), _served_unit("B"), _served_unit("C"))
    edges = tuple(_edge(u, goal) for u in units)
    grouped = group_units_by_goal(units, (goal,), edges)
    assert len(grouped.groups) == 1
    assert grouped.groups[0].outcome_id == goal.id
    assert len(grouped.groups[0].units) == 3
    assert grouped.unlinked == ()


# --- D199/S101: the measurable-outcome fields ride the grouped read -------
# The Map renders the outcome distinct from the goal; the fields are carried
# (propagated from the :Outcome node), not recomputed. One test per mode.

def test_group_carries_progressive_outcome_measure():
    goal = _progressive_goal("German", lever_commitment_id=uuid4())
    units = (_served_unit("Practice"),)
    grouped = group_units_by_goal(units, (goal,), (_edge(units[0], goal),))
    grp = grouped.groups[0]
    assert grp.mode == "progressive"
    assert grp.ladder == ("A1", "A2", "B1")
    assert grp.current_target_level == "A2"
    # A progressive goal carries no sequence terminal.
    assert grp.terminal_target is None
    assert grp.terminal_state is None


def test_group_carries_sequence_outcome_measure():
    goal = _domain_goal(
        name="Get a job", domain="work", mode=GoalMode.SEQUENCE,
        steps=(LeverStep(commitment_id=uuid4(), order=1, state=StepState.READY),),
    )
    units = (_served_unit("Interview"),)
    grouped = group_units_by_goal(units, (goal,), (_edge(units[0], goal),))
    grp = grouped.groups[0]
    assert grp.mode == "sequence"
    assert grp.terminal_target == "Offer accepted"
    assert grp.terminal_state == "pending"
    # A sequence goal carries no progressive ladder.
    assert grp.ladder == ()
    assert grp.current_target_level is None


def test_group_carries_homeostatic_mode_with_no_target_fields():
    # A homeostatic goal's measure is the rhythm held (read from the verdict),
    # so it carries the mode but neither a ladder nor a terminal.
    goal = _domain_goal(
        name="Litany", domain="personal", lever_commitment_id=uuid4()
    )
    units = (_served_unit("Litany"),)
    grouped = group_units_by_goal(units, (goal,), (_edge(units[0], goal),))
    grp = grouped.groups[0]
    assert grp.mode == "homeostatic"
    assert grp.ladder == ()
    assert grp.current_target_level is None
    assert grp.terminal_target is None
    assert grp.terminal_state is None


# --- D187/S92: per-goal status flows through group_units_by_goal ----------

def test_distinct_units_cap_to_a_head_plus_a_counted_tail():
    # D190: a long list of distinct units → a recent-few head + a counted tail.
    goal = _progressive_goal("German", lever_commitment_id=uuid4())
    units = tuple(_served_unit(f"u{i}") for i in range(9))  # 9 distinct
    edges = tuple(_edge(u, goal) for u in units)
    grouped = group_units_by_goal(units, (goal,), edges)
    grp = grouped.groups[0]
    assert len(grp.units) == 6          # the head (_HEAD_DISTINCT)
    assert grp.units_more == 3          # the counted tail


def test_suggestions_map_into_the_goal_and_a_flood_counts():
    from contexts.daily_driver.domain.facet_suggestion import (
        FacetSuggestion,
        SuggestionKind,
    )

    goal = _progressive_goal("German", lever_commitment_id=uuid4())
    units = tuple(_served_unit(f"u{i}") for i in range(5))
    edges = tuple(_edge(u, goal) for u in units)
    sugg = tuple(
        FacetSuggestion(
            unit_id=u.unit_id, kind=SuggestionKind.BLOCK,
            subject=f"u{i}", suggestion=f"block time for u{i}?",
        )
        for i, u in enumerate(units)
    )
    grouped = group_units_by_goal(units, (goal,), edges, suggestions=sugg)
    grp = grouped.groups[0]
    assert grp.suggestion_total == 5      # all five map to the goal via edges
    assert len(grp.suggestion_head) == 3  # head capped (_SUGGESTION_HEAD)


def test_suggestion_for_an_unrelated_unit_does_not_attach():
    from contexts.daily_driver.domain.facet_suggestion import (
        FacetSuggestion,
        SuggestionKind,
    )

    goal = _progressive_goal("German", lever_commitment_id=uuid4())
    served = _served_unit("served")
    other = _served_unit("other")  # no edge to the goal
    edges = (_edge(served, goal),)
    sugg = (
        FacetSuggestion(unit_id=other.unit_id, kind=SuggestionKind.BLOCK,
                        subject="other", suggestion="block?"),
    )
    grouped = group_units_by_goal((served, other), (goal,), edges, suggestions=sugg)
    assert grouped.groups[0].suggestion_total == 0  # the unrelated suggestion stays out


def test_group_sets_progressive_status_active_from_recent_edge():
    from contexts.daily_driver.domain.goal_assessment import GoalStatus

    _now = datetime(2026, 6, 12, tzinfo=timezone.utc)
    goal = _progressive_goal("German", lever_commitment_id=uuid4())
    unit = _served_unit("A", occurred_at=_now - timedelta(days=3))
    grouped = group_units_by_goal(
        (unit,), (goal,), (_edge(unit, goal),), now=_now
    )
    assert grouped.groups[0].status is GoalStatus.ACTIVE


def test_group_emits_homeostatic_goal_with_no_completions_as_not_tracked():
    # D191: a homeostatic goal whose only lever has no completion surfaces with
    # a not-tracked verdict (the moat doesn't know), not a stalled fabricated
    # from the commitment's age — and still surfaces, not hidden as uncovered
    # (D187). The per-lever evidence shows the lever as not tracked.
    from contexts.daily_driver.domain.commitment import (
        Commitment,
        CommitmentActivity,
    )
    from contexts.daily_driver.domain.goal import ControlAxis, Subject
    from contexts.daily_driver.domain.goal_assessment import GoalStatus

    _now = datetime(2026, 6, 12, tzinfo=timezone.utc)
    cid = uuid4()
    commitment = Commitment(
        id=cid, tenant_id=_TENANT, jurisdiction="eu-west", name="Fitness",
        expected_interval_days=1, authored_by_user_id="op",
        created_at=_now - timedelta(days=365),
    )
    goal = Goal(
        id=uuid4(), tenant_id=_TENANT, jurisdiction="eu-west", name="Strength",
        mode=GoalMode.HOMEOSTATIC, control=ControlAxis.SELF, subject=Subject.SELF,
        lever_commitment_ids=(cid,),
    )
    grouped = group_units_by_goal(
        (), (goal,), (), now=_now,
        commitment_activities={
            cid: CommitmentActivity(commitment=commitment, last_completed_at=None)
        },
    )
    assert len(grouped.groups) == 1
    assert grouped.groups[0].status is GoalStatus.NOT_TRACKED
    assert grouped.groups[0].units == ()
    # D191: the lever surfaces as not-tracked in the per-lever evidence.
    assert len(grouped.groups[0].levers) == 1
    assert grouped.groups[0].levers[0].name == "Fitness"
    assert grouped.groups[0].levers[0].status is GoalStatus.NOT_TRACKED


def test_group_folds_a_recurring_series_to_one_row():
    # D175 applied before grouping: ~N instances of one series → one row.
    goal = _progressive_goal("Meds", lever_commitment_id=uuid4())
    insts = tuple(_served_unit("Dose", series_id="rec-1") for _ in range(5))
    edges = tuple(_edge(u, goal) for u in insts)
    grouped = group_units_by_goal(insts, (goal,), edges)
    rows = grouped.groups[0].units
    assert len(rows) == 1
    assert rows[0].instance_count == 5


def test_orphans_land_in_unlinked_none_dropped():
    goal = _progressive_goal("German", lever_commitment_id=uuid4())
    served = _served_unit("German practice")
    o1, o2 = _served_unit("Budget review"), _served_unit("Call bank")
    grouped = group_units_by_goal((served, o1, o2), (goal,), (_edge(served, goal),))
    assert {r.title for r in grouped.unlinked} == {"Budget review", "Call bank"}
    # the unlinked count equals the orphan count; none dropped
    assert len(grouped.unlinked) == 2


def test_no_coverage_suppresses_unlinked_and_groups():
    # D171: outside the coverage boundary, an unlinked unit is unproven, withheld.
    goal = _progressive_goal("German", lever_commitment_id=uuid4())
    grouped = group_units_by_goal((_served_unit("Budget review"),), (goal,), ())
    assert grouped.coverage.has_coverage is False
    assert grouped.unlinked == ()
    assert grouped.groups == ()


def test_groups_follow_canonical_goal_order():
    g1 = _progressive_goal("Alpha", lever_commitment_id=uuid4())
    g2 = _progressive_goal("Beta", lever_commitment_id=uuid4())
    ua, ub = _served_unit("a"), _served_unit("b")
    grouped = group_units_by_goal(
        (ua, ub), (g1, g2), (_edge(ua, g1), _edge(ub, g2))
    )
    assert [g.name for g in grouped.groups] == ["Alpha", "Beta"]


def test_within_group_orders_by_time_then_title():
    goal = _progressive_goal("German", lever_commitment_id=uuid4())
    later = _served_unit("Z", occurred_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    earlier = _served_unit("A", occurred_at=datetime(2026, 6, 1, tzinfo=timezone.utc))
    grouped = group_units_by_goal(
        (later, earlier), (goal,), (_edge(later, goal), _edge(earlier, goal))
    )
    assert [r.title for r in grouped.groups[0].units] == ["A", "Z"]


def test_confirmed_flag_reflects_serving_edge_status():
    goal = _progressive_goal("German", lever_commitment_id=uuid4())
    conf, cand = _served_unit("conf"), _served_unit("cand")
    grouped = group_units_by_goal(
        (conf, cand), (goal,),
        (_edge(conf, goal, LinkStatus.CONFIRMED),
         _edge(cand, goal, LinkStatus.CANDIDATE, "goal-name")),
    )
    by_title = {r.title: r for r in grouped.groups[0].units}
    assert by_title["conf"].confirmed is True
    assert by_title["cand"].confirmed is False


def test_grouped_row_holds_one_signal_per_channel():
    # Three-channel discipline (D180 / design-language §2): tier (domain) rides
    # the group, category (facet_types) and status (confirmed) ride the row.
    # The row carries no domain, so colour (tier) and icon (category) can never
    # duplicate the same signal across channels.
    row_fields = {f.name for f in fields(GroupedUnit)}
    group_fields = {f.name for f in fields(GoalGroup)}
    assert "domain" not in row_fields       # tier is not on the row
    assert "facet_types" in row_fields       # category channel
    assert "confirmed" in row_fields         # status channel
    assert "domain" in group_fields          # tier rides the group


def test_grouped_row_facet_types_are_the_category_channel():
    goal = _progressive_goal("Project", lever_commitment_id=uuid4())
    u = UnitView(
        unit_id=uuid4(), title="Cross-tool unit",
        facets=(
            UnitFacetView(
                facet_type=FacetType.MEETING, facet_id=uuid4(), title="m",
                occurred_at=None, status=LinkStatus.CONFIRMED, confidence=1.0,
                basis="anchor", present=True,
            ),
            UnitFacetView(
                facet_type=FacetType.TASK, facet_id=uuid4(), title="t",
                occurred_at=None, status=LinkStatus.CONFIRMED, confidence=1.0,
                basis="anchor", present=True,
            ),
        ),
    )
    grouped = group_units_by_goal((u,), (goal,), (_edge(u, goal),))
    row = grouped.groups[0].units[0]
    # Deduped + priority-ordered (task before meeting).
    assert row.facet_types == ("task", "meeting")
    assert row.facet_count == 2


# --- D183/S89: the classifier-fed Get-a-job edge + the dedup tiebreak --------

def _email_unit(facet_id, *, present=True):
    return UnitView(
        unit_id=uuid4(), title="job-search email",
        facets=(UnitFacetView(
            facet_type=FacetType.EMAIL, facet_id=facet_id, title="Your application",
            occurred_at=None, status=LinkStatus.CONFIRMED, confidence=1.0,
            basis="anchor", present=present),),
    )


def test_infer_email_edges_confirmed_email_yields_one_confirmed_edge():
    from contexts.daily_driver.domain.goal_assessment import (
        infer_email_job_search_edges,
    )
    goal_id, fid = uuid4(), uuid4()
    edges = infer_email_job_search_edges(
        (_email_unit(fid),), goal_id, frozenset({fid})
    )
    assert len(edges) == 1
    e = edges[0]
    assert e.outcome_id == goal_id
    assert e.status is LinkStatus.CONFIRMED
    assert e.basis == "email-job-search"
    assert e.confidence >= 0.9


def test_infer_email_edges_unconfirmed_email_yields_nothing():
    from contexts.daily_driver.domain.goal_assessment import (
        infer_email_job_search_edges,
    )
    fid = uuid4()
    # the email facet exists but is NOT in the confirmed set -> no edge
    edges = infer_email_job_search_edges(
        (_email_unit(fid),), uuid4(), frozenset()
    )
    assert edges == ()


def test_dedup_prefers_email_job_search_basis_over_title_match():
    from contexts.daily_driver.domain.goal_assessment import dedup_goal_edges
    u, g = uuid4(), uuid4()
    title_edge = GoalEdge(unit_id=u, outcome_id=g, confidence=0.9,
                          status=LinkStatus.CONFIRMED, basis="commitment")
    email_edge = GoalEdge(unit_id=u, outcome_id=g, confidence=0.95,
                          status=LinkStatus.CONFIRMED, basis="email-job-search")
    out = dedup_goal_edges((title_edge, email_edge))
    assert len(out) == 1 and out[0].basis == "email-job-search"
    # order-independent: email edge wins even when it comes first
    out2 = dedup_goal_edges((email_edge, title_edge))
    assert len(out2) == 1 and out2[0].basis == "email-job-search"


# --- D183/S89: the count-by-kind fold + the recency-active reading -----------

def _email_unit_at(facet_id, *, occurred_at):
    return UnitView(
        unit_id=uuid4(), title="job-search email",
        facets=(UnitFacetView(
            facet_type=FacetType.EMAIL, facet_id=facet_id, title="Your application",
            occurred_at=occurred_at, status=LinkStatus.CONFIRMED, confidence=1.0,
            basis="anchor", present=True),),
    )


def test_email_units_fold_to_a_count_by_kind_not_rows():
    goal = _progressive_goal("Get a job", lever_commitment_id=uuid4())
    f1, f2, f3 = uuid4(), uuid4(), uuid4()
    units = (_email_unit(f1), _email_unit(f2), _email_unit(f3))
    edges = tuple(_edge(u, goal, basis="email-job-search") for u in units)
    grouped = group_units_by_goal(
        units, (goal,), edges,
        email_kinds={f1: "application", f2: "application", f3: "interview"},
    )
    grp = grouped.groups[0]
    # the seriesless emails collapse — no per-email rows, a count by kind instead
    assert grp.units == ()
    assert dict(grp.email_activity) == {"application": 2, "interview": 1}


def test_folded_count_equals_the_confirmed_email_total():
    goal = _progressive_goal("Get a job", lever_commitment_id=uuid4())
    fids = [uuid4() for _ in range(5)]
    units = tuple(_email_unit(f) for f in fids)
    edges = tuple(_edge(u, goal, basis="email-job-search") for u in units)
    grouped = group_units_by_goal(
        units, (goal,), edges, email_kinds={f: "application" for f in fids},
    )
    total = sum(c for _, c in grouped.groups[0].email_activity)
    assert total == 5


def test_goal_reads_active_on_recent_email_activity():
    goal = _progressive_goal("Get a job", lever_commitment_id=uuid4())
    now = datetime(2026, 6, 12, tzinfo=timezone.utc)
    f = uuid4()
    recent = _email_unit_at(f, occurred_at=now - timedelta(days=3))
    grouped = group_units_by_goal(
        (recent,), (goal,), (_edge(recent, goal, basis="email-job-search"),),
        email_kinds={f: "interview"}, now=now,
    )
    assert grouped.groups[0].active is True


def test_goal_reads_inactive_when_email_activity_is_stale():
    goal = _progressive_goal("Get a job", lever_commitment_id=uuid4())
    now = datetime(2026, 6, 12, tzinfo=timezone.utc)
    f = uuid4()
    stale = _email_unit_at(f, occurred_at=now - timedelta(days=120))
    grouped = group_units_by_goal(
        (stale,), (goal,), (_edge(stale, goal, basis="email-job-search"),),
        email_kinds={f: "application"}, now=now,
    )
    # presence of 1 (or 335) units is not activity — recency is (the guard)
    grp = grouped.groups[0]
    assert dict(grp.email_activity) == {"application": 1}
    assert grp.active is False


# --- S103e (D205): archived goals scope out; coverage stays honest -----------
# The adapter scopes list_goals to active goals (archived_at IS NULL), so the
# `goals` set the projections receive is active-only. A unit whose only edge
# points to an archived (now-absent) goal must read UNLINKED, not vanish — the
# coverage-honest read (D171). These tests model "the goal was archived" as
# "the goal is absent from `goals` while its edge survives in `edges`".


def test_assess_unit_bound_only_to_archived_goal_reads_unlinked():
    active = _progressive_goal("Get a job", lever_commitment_id=uuid4())
    archived = _progressive_goal("German", lever_commitment_id=uuid4())
    active_unit = _served_unit("Apply to target roles")
    archived_unit = _served_unit("German practice")
    edges = (_edge(active_unit, active), _edge(archived_unit, archived))
    # Only the active goal is in the set (the archived one scoped out upstream).
    assessment = assess_goals((active_unit, archived_unit), (active,), edges)
    # The active goal is covered; the archived-goal unit is an honest orphan.
    assert assessment.coverage.goals_total == 1
    assert assessment.coverage.units_linked == 1  # not 2 — the archived bind
    assert assessment.coverage.has_coverage
    orphan_ids = {o.outcome_id for o in assessment.uncovered_goals}
    assert archived.id not in orphan_ids  # not rendered at all, not "uncovered"
    orphan_titles = {o.title for o in assessment.orphan_work}
    assert "German practice" in orphan_titles


def test_group_unit_bound_only_to_archived_goal_falls_to_unlinked():
    active = _progressive_goal("Get a job", lever_commitment_id=uuid4())
    archived = _progressive_goal("Strength", lever_commitment_id=uuid4())
    active_unit = _served_unit("Recruiter call")
    archived_unit = _served_unit("Deadlift session")
    edges = (_edge(active_unit, active), _edge(archived_unit, archived))
    grouped = group_units_by_goal(
        (active_unit, archived_unit), (active,), edges
    )
    # Only the active goal renders; the archived goal is gone entirely.
    rendered = {g.outcome_id for g in grouped.groups}
    assert rendered == {active.id}
    # The archived-goal unit is not hidden — it swells the unlinked pile.
    unlinked_titles = {u.title for u in grouped.unlinked}
    assert "Deadlift session" in unlinked_titles
    assert grouped.coverage.units_linked == 1


def test_get_a_job_still_renders_and_counts_linked_after_rescope():
    # The retained goal is unaffected: it renders and its units read linked.
    active = _progressive_goal("Get a job", lever_commitment_id=uuid4())
    units = (_served_unit("Application sent"), _served_unit("Interview prep"))
    edges = tuple(_edge(u, active) for u in units)
    grouped = group_units_by_goal(units, (active,), edges)
    assert len(grouped.groups) == 1
    assert grouped.groups[0].outcome_id == active.id
    assert len(grouped.groups[0].units) == 2
    assert grouped.unlinked == ()
    assessment = assess_goals(units, (active,), edges)
    assert assessment.coverage.units_linked == 2
    assert assessment.coverage.goals_covered == 1
