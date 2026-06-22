"""The element-evidence matcher: binding, multi-attach, derive, conservation (D202, S103b).

Pure-domain tests for ``infer_element_evidence`` (lexical+alias per-element recall,
multi-attach, alias→outcome fallback, park-unbound), ``derive_goal_edges`` (the
goal-level rollup), ``summarise_element_evidence`` (the read-only display counts +
unbound bucket), and the conservation invariant (every unit ends bound or unbound,
none lost). Synthetic fixtures — no PII.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from contexts.daily_driver.domain.goal_assessment import (
    ElementEvidence,
    ElementTarget,
    GoalElementTargets,
    derive_goal_edges,
    dedup_element_evidence,
    infer_element_evidence,
    infer_email_job_search_evidence,
    summarise_element_evidence,
)
from contexts.daily_driver.domain.unit_view import UnitFacetView, UnitView
from contexts.daily_driver.domain.work_unit import FacetType, LinkStatus


def _view(title: str, *, facet_type: FacetType = FacetType.TASK) -> UnitView:
    fid = uuid4()
    return UnitView(
        unit_id=uuid4(),
        title=title,
        facets=(
            UnitFacetView(
                facet_type=facet_type, facet_id=fid, title=title,
                occurred_at=None, status=LinkStatus.CONFIRMED, confidence=1.0,
                basis="anchor", present=True,
            ),
        ),
    )


def _goal(
    *, name: str, elements: tuple[ElementTarget, ...] = (),
    expected_outcome: str = "", aliases: tuple[str, ...] = (),
    outcome_id: UUID | None = None,
) -> GoalElementTargets:
    return GoalElementTargets(
        outcome_id=outcome_id or uuid4(), name=name, aliases=aliases,
        elements=elements, expected_outcome=expected_outcome,
    )


# --- binding tiers ----------------------------------------------------------

def test_lexical_exact_binds_confirmed():
    lever = ElementTarget(kind="lever", element_id=uuid4(), label="Apply to roles")
    goal = _goal(name="Get a job", elements=(lever,))
    ev = infer_element_evidence((_view("Apply to roles"),), (goal,))
    assert len(ev) == 1
    assert ev[0].element_id == lever.element_id
    assert ev[0].tier == "lexical_exact" and ev[0].status is LinkStatus.CONFIRMED
    assert ev[0].basis == "element-exact"


def test_keyword_binds_candidate():
    inter = ElementTarget(kind="intermediary", element_id=uuid4(), label="Application response rate")
    goal = _goal(name="Get a job", elements=(inter,))
    ev = infer_element_evidence((_view("Drafted application for Acme"),), (goal,))
    assert len(ev) == 1
    assert ev[0].tier == "lexical_keyword" and ev[0].status is LinkStatus.CANDIDATE


def test_outcome_element_matches_on_expected_outcome():
    goal = _goal(name="Get a job", expected_outcome="Offer accepted")
    ev = infer_element_evidence((_view("Offer accepted"),), (goal,))
    assert len(ev) == 1
    assert ev[0].element_kind == "outcome"
    assert ev[0].element_id == goal.outcome_id


def test_multi_attach_one_unit_several_elements():
    lever = ElementTarget(kind="lever", element_id=uuid4(), label="Apply to roles")
    inter = ElementTarget(kind="intermediary", element_id=uuid4(), label="Apply")
    goal = _goal(name="Get a job", elements=(lever, inter))
    ev = infer_element_evidence((_view("Apply to roles"),), (goal,))
    bound = {e.element_id for e in ev}
    assert lever.element_id in bound and inter.element_id in bound  # both
    assert len(ev) == 2


def test_alias_falls_back_to_outcome_only_when_no_element_matched():
    lever = ElementTarget(kind="lever", element_id=uuid4(), label="Long run")
    goal = _goal(name="Marathon", elements=(lever,))
    ev = infer_element_evidence((_view("Marathon training plan"),), (goal,))
    assert len(ev) == 1
    assert ev[0].element_kind == "outcome" and ev[0].tier == "alias"
    assert ev[0].basis == "goal-name"  # the weak signal the D185/D186 hooks read


def test_no_match_parks_unbound():
    lever = ElementTarget(kind="lever", element_id=uuid4(), label="Long run")
    goal = _goal(name="Marathon", elements=(lever,))
    ev = infer_element_evidence((_view("Unrelated dentist appointment"),), (goal,))
    assert ev == ()  # no row -> unbound


def test_alias_substring_only_no_shared_token_does_not_bind():
    # S103d/D204 precision: "prunes" contains the substring "run", which the old
    # alias rule bound to the outcome — but they share no significant token, so
    # the read-side called it baseless. The matcher now parks it unbound.
    lever = ElementTarget(kind="lever", element_id=uuid4(), label="Long run")
    goal = _goal(name="Run", elements=(lever,))
    ev = infer_element_evidence((_view("Buy prunes"),), (goal,))
    assert ev == ()  # no substring-only alias bind to the outcome


def test_alias_shared_token_still_binds_outcome():
    # S103d/D204 recall: a genuine shared token still falls back to the outcome.
    lever = ElementTarget(kind="lever", element_id=uuid4(), label="Long run")
    goal = _goal(name="Marathon", elements=(lever,))
    ev = infer_element_evidence((_view("Marathon training plan"),), (goal,))
    assert len(ev) == 1
    assert ev[0].element_kind == "outcome" and ev[0].tier == "alias"


# --- dedup + derive ---------------------------------------------------------

def test_dedup_keeps_best_tier_for_same_element():
    eid = uuid4(); o = uuid4(); u = uuid4()
    raw = [
        ElementEvidence(u, "lever", eid, o, "lexical_keyword", LinkStatus.CANDIDATE, "element-keyword"),
        ElementEvidence(u, "lever", eid, o, "lexical_exact", LinkStatus.CONFIRMED, "element-exact"),
    ]
    out = dedup_element_evidence(raw)
    assert len(out) == 1 and out[0].tier == "lexical_exact"


def test_derive_goal_edges_rolls_multi_attach_to_one_best_edge():
    u, o = uuid4(), uuid4()
    ev = (
        ElementEvidence(u, "lever", uuid4(), o, "lexical_keyword", LinkStatus.CANDIDATE, "element-keyword"),
        ElementEvidence(u, "intermediary", uuid4(), o, "lexical_exact", LinkStatus.CONFIRMED, "element-exact"),
    )
    edges = derive_goal_edges(ev)
    assert len(edges) == 1  # one goal edge for the (unit, goal)
    assert edges[0].status is LinkStatus.CONFIRMED  # strongest wins


def test_derive_distinct_goals_distinct_edges():
    u = uuid4()
    ev = (
        ElementEvidence(u, "lever", uuid4(), uuid4(), "lexical_exact", LinkStatus.CONFIRMED, "element-exact"),
        ElementEvidence(u, "lever", uuid4(), uuid4(), "lexical_exact", LinkStatus.CONFIRMED, "element-exact"),
    )
    assert len(derive_goal_edges(ev)) == 2


# --- summary + conservation -------------------------------------------------

def test_summarise_counts_and_unbound_bucket():
    eid = uuid4(); o = uuid4(); u1, u2 = uuid4(), uuid4()
    ev = (
        ElementEvidence(u1, "lever", eid, o, "lexical_exact", LinkStatus.CONFIRMED, "element-exact"),
        ElementEvidence(u2, "lever", eid, o, "lexical_exact", LinkStatus.CONFIRMED, "element-exact"),
    )
    s = summarise_element_evidence(ev, total_units=5)
    assert dict(s.counts)[eid] == 2
    assert s.bound_units == 2 and s.unbound_units == 3 and s.total_units == 5


def test_conservation_every_unit_bound_or_unbound_none_lost():
    # AC5: the re-match leaves every unit either carrying evidence or unbound.
    lever = ElementTarget(kind="lever", element_id=uuid4(), label="Long run")
    goal = _goal(name="Marathon", elements=(lever,))
    units = (_view("Long run"), _view("Marathon training plan"), _view("Dentist"))
    ev = infer_element_evidence(units, (goal,))
    s = summarise_element_evidence(ev, total_units=len(units))
    # bound + unbound partitions the corpus exactly — nothing dropped
    assert s.bound_units + s.unbound_units == len(units)
    bound_unit_ids = {e.unit_id for e in ev}
    assert s.bound_units == len(bound_unit_ids)
    # "Long run" binds (exact), "Marathon training plan" binds (alias), "Dentist" unbound
    assert s.bound_units == 2 and s.unbound_units == 1


def test_migration_0006_declares_the_evidences_edge_index():
    # The live-surface law's minimum standing guard: 0006 carries the EVIDENCES
    # relationship index so drift between the matcher's edge and the schema fails
    # here rather than in production.
    text = Path("migrations/neo4j/0006_element_evidence.cypher").read_text()
    assert "EVIDENCES" in text
    assert "evidences_tenant_id" in text and "IF NOT EXISTS" in text


def test_email_job_search_evidence_binds_to_outcome():
    o = uuid4(); fid = uuid4()
    unit = UnitView(
        unit_id=uuid4(), title="Re: your application",
        facets=(
            UnitFacetView(
                facet_type=FacetType.EMAIL, facet_id=fid, title="Re: your application",
                occurred_at=None, status=LinkStatus.CONFIRMED, confidence=1.0,
                basis="anchor", present=True,
            ),
        ),
    )
    ev = infer_email_job_search_evidence((unit,), o, frozenset({fid}))
    assert len(ev) == 1
    assert ev[0].element_kind == "outcome" and ev[0].element_id == o
    assert ev[0].basis == "email-job-search" and ev[0].status is LinkStatus.CONFIRMED
