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


def test_three_way_split_rejected_engaged_and_one_touch_grain():
    opps = (
        _opp(status="closed", reason="rejected"),
        _opp(status="closed", reason="rejected"),
        _opp(status="closed", reason="went_cold"),
        _opp(status="live"),
    )
    s = build_pipeline_stats(opportunities=opps, one_touch_volume=102, now=_NOW)
    assert s.rejected.count == 2
    assert s.engaged.count == 2  # the cold + the live (non-rejected)
    assert s.no_response.count == 102 and s.no_response.opportunity_ids == ()  # grain: count only


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
