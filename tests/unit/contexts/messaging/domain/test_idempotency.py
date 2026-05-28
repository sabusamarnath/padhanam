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


@pytest.mark.parametrize(
    "trigger_type",
    [
        BroadcastTriggerType.THRESHOLD_CROSSED,
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
