"""EmailSyncTrigger — the trigger-agnostic seam for the email pull (D151).

The pull pipeline takes its trigger as a plain parameter (a poll drives it
today; a future webhook would drive the same function), mirroring
calendar's CalendarSyncTrigger. Recorded for observability; it does not
branch the pull logic. Framework-free per D16.
"""

from __future__ import annotations

from enum import StrEnum


class EmailSyncTrigger(StrEnum):
    POLL = "poll"


__all__ = ["EmailSyncTrigger"]
