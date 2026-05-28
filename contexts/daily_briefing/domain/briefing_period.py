"""BriefingPeriod value object — the daily-briefing window (D146, S54).

The look-back window the briefing composes over. Carried on
DailyBriefingResponse as the ``briefing_period`` extension field so the
channel render can surface a "Daily briefing for [window]" header per
D135.

Domain layer per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BriefingPeriod:
    """The [window_start, window_end] look-back the briefing composed over."""

    window_start: datetime
    window_end: datetime

    def __post_init__(self) -> None:
        if self.window_end <= self.window_start:
            raise ValueError(
                "BriefingPeriod.window_end must be strictly after window_start; "
                f"got start={self.window_start.isoformat()} "
                f"end={self.window_end.isoformat()}"
            )


__all__ = ["BriefingPeriod"]
