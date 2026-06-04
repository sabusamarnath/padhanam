"""Render-time staleness rule for Commitments (D157).

Pure functions over (last-activity timestamp, expected interval, now).
``now`` is injected by the application layer so the domain stays
deterministic and testable — the daily-driver surface computes overdue
at render from elapsed-since-last-completion, with no persisted overdue
flag (D157).

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from datetime import datetime

_SECONDS_PER_DAY = 86_400


def days_elapsed(*, since: datetime, now: datetime) -> int:
    """Whole days elapsed from ``since`` to ``now`` (floored, never negative)."""
    delta_seconds = (now - since).total_seconds()
    if delta_seconds <= 0:
        return 0
    return int(delta_seconds // _SECONDS_PER_DAY)


def is_overdue(
    *, last_activity_at: datetime, expected_interval_days: int, now: datetime
) -> bool:
    """True when more than ``expected_interval_days`` have elapsed."""
    return (
        days_elapsed(since=last_activity_at, now=now) > expected_interval_days
    )


def overdue_by_days(
    *, last_activity_at: datetime, expected_interval_days: int, now: datetime
) -> int:
    """How many days past the interval, or 0 when not overdue."""
    overshoot = (
        days_elapsed(since=last_activity_at, now=now) - expected_interval_days
    )
    return overshoot if overshoot > 0 else 0


__all__ = ["days_elapsed", "is_overdue", "overdue_by_days"]
