"""The match use cases — run stores, never writes fit_tier; accept promotes; stale
recomputes on read; confirmed-only + tenant isolation (S103ag, D239)."""

from __future__ import annotations

import asyncio
from uuid import uuid4, uuid5, NAMESPACE_URL as NS

from contexts.daily_driver.application.opportunity_match import (
    accept_fit_tier_suggestion,
    read_opportunity_match,
    run_opportunity_match,
)
from contexts.daily_driver.domain.matching import CriterionCoverage
from contexts.daily_driver.domain.skills import SkillItemView
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000a001"


def _actor() -> ActorContext:
    roles = frozenset({"operator"})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001", role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


class _FakeGraph:
    def __init__(self, *, criteria="- SQL\n- Leadership\n- Pricing", fit_tier="opportunistic"):
        self.store = {
            "fit_tier": fit_tier, "fit_tier_suggested": None, "match_result": None,
            "match_ran_at": None, "match_inputs_hash": None,
            "selection_criteria": criteria, "selection_criteria_ts": "t0",
        }
        self.items = (
            SkillItemView(item_id=uuid5(NS, "a"), kind="skill", text="SQL",
                          proof_state="confirmed", provenance_origin="cv_extraction"),
            SkillItemView(item_id=uuid5(NS, "b"), kind="experience", text="Led a team",
                          proof_state="confirmed", provenance_origin="cv_extraction"),
            # a SUGGESTED item that must NOT reach the match (confirmed-only)
            SkillItemView(item_id=uuid5(NS, "c"), kind="skill", text="unconfirmed",
                          proof_state="suggested", provenance_origin="cv_extraction"),
        )
        self.tenants_seen: list[str] = []
        self.fit_tier_writes: list[str] = []   # the guard: run must NOT write here

    async def read_opportunity_match(self, *, tenant_context, opportunity_id):
        self.tenants_seen.append(tenant_context.tenant_id)
        return dict(self.store)

    async def list_skill_items(self, *, tenant_context):
        self.tenants_seen.append(tenant_context.tenant_id)
        return self.items

    async def set_opportunity_match(self, *, tenant_context, opportunity_id,
                                    result_json, fit_tier_suggested, inputs_hash):
        self.tenants_seen.append(tenant_context.tenant_id)
        self.store["match_result"] = result_json
        self.store["fit_tier_suggested"] = fit_tier_suggested
        self.store["match_inputs_hash"] = inputs_hash
        self.store["match_ran_at"] = "t1"
        return True

    async def set_opportunity_fit_tier(self, *, tenant_context, opportunity_id, fit_tier):
        self.tenants_seen.append(tenant_context.tenant_id)
        self.fit_tier_writes.append(fit_tier)
        self.store["fit_tier"] = fit_tier
        return True


class _FakeMatch:
    """Returns strength for SQL, gap for the rest — and asserts confirmed-only."""

    def __init__(self):
        self.seen_skills = None

    async def match(self, *, criteria, skills, experiences):
        self.seen_skills = skills
        return tuple(
            CriterionCoverage(
                criterion=c,
                band="strength" if c == "SQL" else "gap",
                evidence="SQL listed" if c == "SQL" else "",
            )
            for c in criteria
        )


def test_run_matches_confirmed_only_and_never_writes_fit_tier() -> None:
    """AC1/AC2/AC4/AC6 — run produces per-criterion bands from the confirmed profile
    only, and never writes fit_tier directly (only fit_tier_suggested)."""
    graph, match = _FakeGraph(), _FakeMatch()
    opp = uuid4()
    view = asyncio.run(run_opportunity_match(
        goal_graph=graph, match_port=match, actor=_actor(), opportunity_id=opp,
    ))
    # the suggested item was excluded (confirmed-only)
    assert match.seen_skills == ("SQL",)
    assert view.has_result and view.band_counts == {"strength": 1, "partial": 0, "gap": 2}
    # the match wrote a suggestion but NEVER fit_tier
    assert graph.store["fit_tier_suggested"] is not None
    assert graph.fit_tier_writes == []            # THE GUARD (AC4)
    assert graph.store["fit_tier"] == "opportunistic"  # unchanged
    # tenant isolation — every call carried the actor's tenant
    assert set(graph.tenants_seen) == {_TENANT}


def test_run_with_no_criteria_stores_nothing() -> None:
    graph, match = _FakeGraph(criteria=""), _FakeMatch()
    view = asyncio.run(run_opportunity_match(
        goal_graph=graph, match_port=match, actor=_actor(), opportunity_id=uuid4(),
    ))
    assert view.has_criteria is False and view.has_result is False
    assert graph.store["match_result"] is None


def test_read_flags_stale_when_criteria_change_after_run() -> None:
    """AC5 — after a run, editing the criteria makes the read report stale."""
    graph, match = _FakeGraph(), _FakeMatch()
    opp = uuid4()
    fresh = asyncio.run(run_opportunity_match(
        goal_graph=graph, match_port=match, actor=_actor(), opportunity_id=opp,
    ))
    assert fresh.stale is False
    graph.store["selection_criteria"] += "\n- A new requirement"
    later = asyncio.run(read_opportunity_match(
        goal_graph=graph, actor=_actor(), opportunity_id=opp,
    ))
    assert later.stale is True


def test_read_flags_stale_when_profile_changes_after_run() -> None:
    graph, match = _FakeGraph(), _FakeMatch()
    opp = uuid4()
    asyncio.run(run_opportunity_match(
        goal_graph=graph, match_port=match, actor=_actor(), opportunity_id=opp,
    ))
    # confirm a previously-suggested item -> the confirmed profile changed
    graph.items = graph.items + (
        SkillItemView(item_id=uuid5(NS, "d"), kind="skill", text="New skill",
                      proof_state="confirmed", provenance_origin="cv_extraction"),
    )
    later = asyncio.run(read_opportunity_match(
        goal_graph=graph, actor=_actor(), opportunity_id=opp,
    ))
    assert later.stale is True


def test_accept_promotes_suggestion_to_fit_tier() -> None:
    """AC — accept promotes fit_tier_suggested to fit_tier; nothing to accept -> False."""
    graph = _FakeGraph(fit_tier="bullseye")
    graph.store["fit_tier_suggested"] = "strong"
    ok = asyncio.run(accept_fit_tier_suggestion(
        goal_graph=graph, actor=_actor(), opportunity_id=uuid4(),
    ))
    assert ok is True and graph.store["fit_tier"] == "strong"
    assert graph.fit_tier_writes == ["strong"]


def test_accept_with_no_suggestion_is_a_noop() -> None:
    graph = _FakeGraph()
    graph.store["fit_tier_suggested"] = None
    ok = asyncio.run(accept_fit_tier_suggestion(
        goal_graph=graph, actor=_actor(), opportunity_id=uuid4(),
    ))
    assert ok is False and graph.fit_tier_writes == []


def test_accepted_flag_true_once_current_equals_suggestion() -> None:
    graph, match = _FakeGraph(fit_tier="opportunistic"), _FakeMatch()
    # 1 strength / 3 -> opportunistic, which equals the current tier
    view = asyncio.run(run_opportunity_match(
        goal_graph=graph, match_port=match, actor=_actor(), opportunity_id=uuid4(),
    ))
    assert view.suggested_fit_tier == "opportunistic"
    assert view.accepted is True
