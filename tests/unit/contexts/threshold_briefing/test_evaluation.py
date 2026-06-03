"""Unit tests for threshold evaluation over calendar state (D153, S57).

The two Phase 2-A must-have rules plus the restraint no-cross case, as
pure functions over MeetingState (D153: state-store evaluation).
"""

from __future__ import annotations

from contexts.threshold_briefing.application.rule_config import phase_2a_rules
from contexts.threshold_briefing.domain.evaluation import (
    detect_cancellations,
    detect_conflicts,
    evaluate,
)
from contexts.threshold_briefing.domain.threshold_rule import (
    ThresholdRule,
    ThresholdRuleType,
)
from tests.unit.contexts.threshold_briefing.conftest import at, make_meeting

_WINDOW_START = at(0)
_WINDOW_END = at(23)


def test_detect_cancellations_matches_cancelled_in_window() -> None:
    meetings = (
        make_meeting(title="Board sync", status="cancelled", cancelled_at=at(9)),
        make_meeting(title="Standup", status="confirmed", start_at=at(10), end_at=at(11)),
    )
    matches = detect_cancellations(
        meetings, rule_id="r", window_start=_WINDOW_START, window_end=_WINDOW_END
    )
    assert len(matches) == 1
    assert matches[0].rule_type is ThresholdRuleType.MEETING_CANCELLED
    assert matches[0].title == "Board sync"
    assert matches[0].cancelled_at == at(9)
    assert "Board sync" in matches[0].summary


def test_detect_cancellations_ignores_cancelled_before_window_start() -> None:
    meetings = (
        make_meeting(title="Old cancel", status="cancelled", cancelled_at=at(9, day=1)),
    )
    matches = detect_cancellations(
        meetings, rule_id="r", window_start=_WINDOW_START, window_end=_WINDOW_END
    )
    assert matches == ()


def test_detect_cancellations_matches_cancelled_after_window_end() -> None:
    """Lower-bound only (S57 live finding): a cancelled_at past window_end still matches.

    The calendar tombstone sets cancelled_at to the refresh time, which —
    under refresh-then-evaluate — lands after the trigger's window_end; an
    upper bound would drop exactly the cancellations the scan must catch.
    """
    meetings = (
        make_meeting(title="Just cancelled", status="cancelled", cancelled_at=at(23, day=4)),
    )
    matches = detect_cancellations(
        meetings, rule_id="r", window_start=_WINDOW_START, window_end=_WINDOW_END
    )
    assert len(matches) == 1


def test_cancellation_identity_excludes_cancelled_at() -> None:
    """The cancellation crossing identity is stable across cancelled_at churn (S57)."""
    m1 = detect_cancellations(
        (make_meeting(title="X", status="cancelled", cancelled_at=at(9), google_event_id="evt-1"),),
        rule_id="r", window_start=_WINDOW_START, window_end=_WINDOW_END,
    )[0]
    m2 = detect_cancellations(
        (make_meeting(title="X", status="cancelled", cancelled_at=at(14), google_event_id="evt-1"),),
        rule_id="r", window_start=_WINDOW_START, window_end=_WINDOW_END,
    )[0]
    # Same event, different cancelled_at (a re-tombstone): same identity → dedupes.
    assert m1.crossing_identity() == m2.crossing_identity() == "r:evt-1"


def test_detect_conflicts_matches_overlapping_confirmed_pair() -> None:
    meetings = (
        make_meeting(title="A", status="confirmed", start_at=at(9), end_at=at(10), google_event_id="a"),
        make_meeting(title="B", status="confirmed", start_at=at(9), end_at=at(10), google_event_id="b"),
        make_meeting(title="C", status="confirmed", start_at=at(11), end_at=at(12), google_event_id="c"),
    )
    matches = detect_conflicts(meetings, rule_id="r")
    assert len(matches) == 1
    m = matches[0]
    assert m.rule_type is ThresholdRuleType.MEETING_CONFLICT
    assert {m.google_event_id, m.partner_event_id} == {"a", "b"}
    # The crossing identity is order-independent (same conflict, either scan).
    assert m.crossing_identity() == "r:a|b"


def test_detect_conflicts_ignores_cancelled_and_non_overlapping() -> None:
    meetings = (
        make_meeting(title="A", status="confirmed", start_at=at(9), end_at=at(10)),
        make_meeting(title="B", status="confirmed", start_at=at(10), end_at=at(11)),  # touch, no overlap
        make_meeting(title="X", status="cancelled", start_at=at(9), end_at=at(10), cancelled_at=at(8)),
    )
    assert detect_conflicts(meetings, rule_id="r") == ()


def test_evaluate_runs_both_active_rules() -> None:
    meetings = (
        make_meeting(title="Cancelled one", status="cancelled", cancelled_at=at(9)),
        make_meeting(title="A", status="confirmed", start_at=at(9), end_at=at(11), google_event_id="a"),
        make_meeting(title="B", status="confirmed", start_at=at(10), end_at=at(12), google_event_id="b"),
    )
    matches = evaluate(
        phase_2a_rules(), meetings, window_start=_WINDOW_START, window_end=_WINDOW_END
    )
    kinds = {m.rule_type for m in matches}
    assert kinds == {ThresholdRuleType.MEETING_CANCELLED, ThresholdRuleType.MEETING_CONFLICT}


def test_evaluate_no_cross_returns_empty_the_restraint_case() -> None:
    """The restraint no-cross case: no matching state change → no crossing."""
    meetings = (
        make_meeting(title="A", status="confirmed", start_at=at(9), end_at=at(10)),
        make_meeting(title="B", status="confirmed", start_at=at(11), end_at=at(12)),
    )
    assert evaluate(
        phase_2a_rules(), meetings, window_start=_WINDOW_START, window_end=_WINDOW_END
    ) == ()


def test_evaluate_skips_deferred_rule_shapes() -> None:
    """A deferred-shape rule carried in config is not evaluated (restraint)."""
    deferred = (
        ThresholdRule(rule_id="m", rule_type=ThresholdRuleType.MEETING_MOVED),
        ThresholdRule(rule_id="e", rule_type=ThresholdRuleType.EMAIL_FROM_SENDER),
    )
    meetings = (
        make_meeting(title="Cancelled", status="cancelled", cancelled_at=at(9)),
    )
    # Even with a real cancellation present, deferred rules match nothing.
    assert evaluate(
        deferred, meetings, window_start=_WINDOW_START, window_end=_WINDOW_END
    ) == ()
