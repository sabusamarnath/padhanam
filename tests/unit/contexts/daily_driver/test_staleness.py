"""Unit tests for the render-time staleness rule (D157)."""

from __future__ import annotations

from datetime import datetime, timezone

from contexts.daily_driver.domain.staleness import (
    days_elapsed,
    is_overdue,
    overdue_by_days,
)


def _dt(day: int) -> datetime:
    return datetime(2026, 6, day, 12, 0, tzinfo=timezone.utc)


def test_days_elapsed_floors_and_never_negative() -> None:
    assert days_elapsed(since=_dt(1), now=_dt(8)) == 7
    assert days_elapsed(since=_dt(8), now=_dt(1)) == 0
    assert days_elapsed(since=_dt(8), now=_dt(8)) == 0


def test_is_overdue_at_boundary() -> None:
    # exactly the interval is not yet overdue; one day past is.
    assert is_overdue(last_activity_at=_dt(1), expected_interval_days=7, now=_dt(8)) is False
    assert is_overdue(last_activity_at=_dt(1), expected_interval_days=7, now=_dt(9)) is True


def test_overdue_by_days_zero_when_on_track() -> None:
    assert overdue_by_days(last_activity_at=_dt(1), expected_interval_days=7, now=_dt(8)) == 0
    assert overdue_by_days(last_activity_at=_dt(1), expected_interval_days=7, now=_dt(11)) == 3
