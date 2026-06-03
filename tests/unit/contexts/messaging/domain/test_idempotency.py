"""Unit tests for the idempotency key resolver (D147, S54)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from contexts.messaging.domain.idempotency import resolve_idempotency_key
from shared_kernel.broadcast_flow import BroadcastTriggerType


_FIXED_NOW = datetime(2026, 5, 28, 2, 30, tzinfo=timezone.utc)


def test_daily_scheduled_returns_operator_date_utc() -> None:
    """DAILY_SCHEDULED resolves to the operator-timezone date string."""
    key = resolve_idempotency_key(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
        metadata={},
        operator_timezone="UTC",
        now=_FIXED_NOW,
    )
    assert key == "2026-05-28"


def test_daily_scheduled_respects_operator_timezone_rollover() -> None:
    """A timezone west of UTC can still be on the previous calendar day."""
    # 02:30 UTC on 2026-05-28 is 22:30 on 2026-05-27 in New York (EDT).
    key = resolve_idempotency_key(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
        metadata={},
        operator_timezone="America/New_York",
        now=_FIXED_NOW,
    )
    assert key == "2026-05-27"


def test_daily_scheduled_same_day_two_fires_resolve_same_key() -> None:
    """Two fires within the same operator day resolve to the same key."""
    morning = datetime(2026, 5, 28, 6, 0, tzinfo=timezone.utc)
    evening = datetime(2026, 5, 28, 20, 0, tzinfo=timezone.utc)
    k1 = resolve_idempotency_key(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
        metadata={},
        operator_timezone="UTC",
        now=morning,
    )
    k2 = resolve_idempotency_key(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
        metadata={},
        operator_timezone="UTC",
        now=evening,
    )
    assert k1 == k2 == "2026-05-28"


def test_manual_returns_none() -> None:
    """MANUAL triggers carry no idempotency key per D147."""
    key = resolve_idempotency_key(
        trigger_type=BroadcastTriggerType.MANUAL,
        metadata={"caller_note": "test fire"},
        operator_timezone="UTC",
        now=_FIXED_NOW,
    )
    assert key is None


def test_scheduled_evaluation_returns_none() -> None:
    """SCHEDULED_EVALUATION is not idempotency-protected (S57, D153).

    The scan runs every cadence tick; dedup is the downstream
    THRESHOLD_CROSSED key, so the scan itself is always fresh.
    """
    key = resolve_idempotency_key(
        trigger_type=BroadcastTriggerType.SCHEDULED_EVALUATION,
        metadata={},
        operator_timezone="UTC",
        now=_FIXED_NOW,
    )
    assert key is None


def test_threshold_crossed_uses_crossing_identity() -> None:
    """THRESHOLD_CROSSED keys on the crossing's derived-state identity (S57).

    The identity is ``rule_id:google_event_id`` for a cancellation — it
    excludes ``cancelled_at`` per D153's live-smoke refinement.
    """
    key = resolve_idempotency_key(
        trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
        metadata={"crossing_identity": "calendar.meeting_cancelled:evt-1"},
        operator_timezone="UTC",
        now=_FIXED_NOW,
    )
    assert key == "calendar.meeting_cancelled:evt-1"
    assert "cancelled_at" not in key


def test_threshold_crossed_key_matches_rulematch_ssot_and_excludes_cancelled_at() -> None:
    """The resolved key equals ``RuleMatch.crossing_identity()`` and omits cancelled_at.

    Binds the messaging idempotency key to the threshold-briefing SSOT
    (``RuleMatch.to_trigger_metadata`` / ``crossing_identity``): a
    cancellation match carrying a populated ``cancelled_at`` still keys on
    ``rule_id:google_event_id``, so a re-scan that churns ``cancelled_at``
    resolves to the same key (no double-brief) — the S57 live-smoke fix.
    """
    from datetime import datetime, timezone
    from uuid import UUID

    from contexts.threshold_briefing.domain.rule_match import RuleMatch
    from contexts.threshold_briefing.domain.threshold_rule import ThresholdRuleType

    match = RuleMatch(
        rule_id="calendar.meeting_cancelled",
        rule_type=ThresholdRuleType.MEETING_CANCELLED,
        google_event_id="evt-1",
        meeting_id=UUID(int=1),
        title="Standup",
        summary="Meeting cancelled: Standup",
        cancelled_at=datetime(2026, 6, 3, 9, 0, tzinfo=timezone.utc),
    )
    key = resolve_idempotency_key(
        trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
        metadata=match.to_trigger_metadata(),
        operator_timezone="UTC",
    )
    assert key == match.crossing_identity() == "calendar.meeting_cancelled:evt-1"

    # A later scan re-tombstones with a churned cancelled_at; the key holds.
    churned = match.to_trigger_metadata()
    churned["cancelled_at"] = "2026-06-03T11:30:00+00:00"
    key_rescan = resolve_idempotency_key(
        trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
        metadata=churned,
        operator_timezone="UTC",
    )
    assert key_rescan == key


def test_threshold_crossed_same_crossing_two_scans_same_key() -> None:
    """The same crossing found on two scans resolves to the same key (no double-brief)."""
    md = {"crossing_identity": "calendar.meeting_conflict:a|b"}
    k1 = resolve_idempotency_key(
        trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
        metadata=md,
        operator_timezone="UTC",
    )
    k2 = resolve_idempotency_key(
        trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
        metadata=dict(md),
        operator_timezone="UTC",
    )
    assert k1 == k2 == "calendar.meeting_conflict:a|b"


def test_threshold_crossed_reconstructs_stable_identity_when_identity_absent() -> None:
    """Absent crossing_identity (the HTTP path) reconstructs the stable shape, no cancelled_at.

    The fallback mirrors ``RuleMatch.crossing_identity()``: a cancellation
    is ``rule_id:google_event_id`` even when ``cancelled_at`` is present in
    the metadata — the timestamp is never embedded in the key.
    """
    key = resolve_idempotency_key(
        trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
        metadata={
            "rule_id": "calendar.meeting_cancelled",
            "google_event_id": "evt-1",
            "cancelled_at": "2026-06-03T09:00:00+00:00",
        },
        operator_timezone="UTC",
    )
    assert key == "calendar.meeting_cancelled:evt-1"
    assert "2026-06-03" not in key


def test_threshold_crossed_reconstructs_conflict_pair_when_identity_absent() -> None:
    """Absent crossing_identity for a conflict reconstructs rule_id + sorted event pair."""
    key = resolve_idempotency_key(
        trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
        metadata={
            "rule_id": "calendar.meeting_conflict",
            "google_event_id": "evt-b",
            "partner_event_id": "evt-a",
        },
        operator_timezone="UTC",
    )
    assert key == "calendar.meeting_conflict:evt-a|evt-b"


@pytest.mark.parametrize(
    "trigger_type",
    [
        BroadcastTriggerType.CALENDAR_EVENT,
        BroadcastTriggerType.EMAIL_RECEIVED,
    ],
)
def test_future_trigger_types_raise_not_implemented(
    trigger_type: BroadcastTriggerType,
) -> None:
    """Trigger types without committed key semantics raise NotImplementedError."""
    with pytest.raises(NotImplementedError):
        resolve_idempotency_key(
            trigger_type=trigger_type,
            metadata={},
            operator_timezone="UTC",
            now=_FIXED_NOW,
        )


def test_unknown_timezone_raises_value_error() -> None:
    """An unknown timezone string surfaces a clear configuration error."""
    with pytest.raises(ValueError, match="unknown operator_timezone"):
        resolve_idempotency_key(
            trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
            metadata={},
            operator_timezone="Mars/Olympus_Mons",
            now=_FIXED_NOW,
        )
