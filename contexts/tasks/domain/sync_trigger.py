"""TaskSyncTrigger — the trigger-agnostic seam, as a value not a Protocol (D167).

Mirrors the calendar/email sync-trigger: the fetch-store-sync pipeline is a
function taking its trigger context as a plain parameter, with one caller today
(the poll). Push (a future webhook) would drive the same function as an added
trigger source (an added enum value), not a second pipeline — the two-threshold
rule's tell returns *wait* until then.
"""

from __future__ import annotations

from enum import StrEnum


class TaskSyncTrigger(StrEnum):
    POLL = "poll"
