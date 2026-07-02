"""S103q/D217: the pure pipeline stats — three-way split, depth ladder, cards,
next-best-action rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from contexts.daily_driver.domain.pipeline_stats import (
    PipelineOpp,
    build_pipeline_stats,
    next_best_action,
)

_NOW = datetime(2026, 6, 30, tzinfo=timezone.utc)


def _opp(*, status="live", reason=None, stage="", order=None, days_ago=2, touches=2):
    return PipelineOpp(
        opportunity_id=uuid4(), company="Co", role="R", status=status,
        closed_reason=reason, stage=stage, gate_order=order,
        last_activity=_NOW - timedelta(days=days_ago), touches=touches,
    )


def test_split_engaged_is_live_only_closed_go_to_their_buckets():
    # S103s-fix: "engaged" = actually engaged (LIVE); a closed went-cold/declined is
    # NOT engaged (it left the pipeline) — it lands in rejected or closed-other, so
    # closing a process drops it out of engaged.
    opps = (
        _opp(status="closed", reason="rejected"),
        _opp(status="closed", reason="rejected"),
        _opp(status="closed", reason="went_cold"),
        _opp(status="closed", reason="declined"),
        _opp(status="live"),
    )
    s = build_pipeline_stats(opportunities=opps, one_touch_volume=102, now=_NOW)
    assert s.rejected.count == 2
    assert s.engaged.count == 1                # only the live one
    assert s.closed_other.count == 2           # went-cold + declined (closed, not rejected)
    assert s.no_response.count == 102 and s.no_response.opportunity_ids == ()  # grain: count only


def _lead(*, company, tier, warm, source="outbound"):
    return PipelineOpp(
        opportunity_id=uuid4(), company=company, role="", status="live",
        closed_reason=None, stage="Lead", gate_order=2, last_activity=None,
        touches=0, fit_tier=tier, warm_access_available=warm,
        origination_source=source,
    )


def test_leads_partitioned_out_and_sorted_fit_then_warm():
    # S103t/D221: a live opportunity at the Lead gate is a lead — origination, not
    # an application — so it is excluded from the engaged split, the depth ladder,
    # and the cards, and surfaced in the leads bucket sorted fit primary (bullseye >
    # strong > opportunistic), warm secondary (warm > cold).
    opps = (
        _lead(company="Zeta", tier="opportunistic", warm="cold"),
        _opp(status="live", stage="Screening", order=4),           # applied, not a lead
        _lead(company="Beta", tier="bullseye", warm="cold"),
        _lead(company="Alpha", tier="bullseye", warm="warm"),
        _lead(company="Gamma", tier="strong", warm="warm"),
    )
    s = build_pipeline_stats(opportunities=opps, one_touch_volume=0, now=_NOW)
    assert [le.company for le in s.leads] == ["Alpha", "Beta", "Gamma", "Zeta"]
    assert s.leads[0].fit_tier == "bullseye" and s.leads[0].warm_access_available == "warm"
    # leads are NOT in the applied funnel / ladder / cards
    assert s.engaged.count == 1                                    # only the Screening one
    assert all(c.stage != "Lead" for c in s.cards)
    assert all(r.stage != "Lead" for r in s.ladder)


def test_no_leads_yields_empty_leads_bucket():
    s = build_pipeline_stats(
        opportunities=(_opp(status="live", stage="Apply", order=3),),
        one_touch_volume=0, now=_NOW,
    )
    assert s.leads == ()


def test_depth_ladder_deepest_first_unplaced_last_includes_rejected():
    apply_g, screen_g = "Apply", "Screening"
    opps = (
        _opp(stage=screen_g, order=4, status="closed", reason="rejected"),  # Acme
        _opp(stage=apply_g, order=3),
        _opp(stage="", order=None),
        _opp(stage="", order=None),
    )
    s = build_pipeline_stats(opportunities=opps, one_touch_volume=0, now=_NOW)
    assert [r.stage for r in s.ladder] == ["Screening", "Apply", "Unplaced"]
    assert s.ladder[0].count == 1 and s.ladder[-1].count == 2
    # the rejected-at-screening still occupies the Screening rung (depth, not outcome)
    assert s.ladder[0].stage == "Screening"


def test_next_best_action_rules():
    # silent applied -> follow up
    assert "follow up" in next_best_action(status="live", closed_reason=None, stage="Apply", days_silent=30)
    # recent applied -> await
    assert "await" in next_best_action(status="live", closed_reason=None, stage="Apply", days_silent=1).lower()
    # in screening, recent -> prepare
    assert "prepare" in next_best_action(status="live", closed_reason=None, stage="Screening", days_silent=2)
    # in screening, silent -> chase
    assert "chase" in next_best_action(status="live", closed_reason=None, stage="Screening", days_silent=40)
    # closed -> reopen if live
    assert "reopen" in next_best_action(status="closed", closed_reason="rejected", stage="Screening", days_silent=5)


def test_cards_carry_days_silent_and_action():
    opps = (_opp(stage="Screening", order=4, days_ago=40),)
    s = build_pipeline_stats(opportunities=opps, one_touch_volume=0, now=_NOW)
    card = s.cards[0]
    assert card.days_silent == 40 and "chase" in card.next_action and card.stage == "Screening"


def test_undated_activity_reads_honestly():
    o = PipelineOpp(
        opportunity_id=uuid4(), company="Co", role="R", status="live",
        closed_reason=None, stage="", gate_order=None, last_activity=None, touches=1,
    )
    s = build_pipeline_stats(opportunities=(o,), one_touch_volume=0, now=_NOW)
    assert s.cards[0].days_silent is None and "No dated activity" in s.cards[0].next_action
