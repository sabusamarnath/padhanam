"""CalendarSyncTrigger — the trigger-agnostic seam, as a value not a Protocol (D148).

The fetch-store-sync pipeline is a function that takes its trigger context
as a plain parameter, with one caller today (the poll). Push (Google
``watch`` -> webhook) is deferred and merely anticipated this phase, so
the two-threshold rule's tell returns *wait*: a webhook would later drive
the same function as an added trigger source (an added enum value), not a
second pipeline, and only then does the trigger boundary earn a Protocol.
"""

from __future__ import annotations

from enum import StrEnum


class CalendarSyncTrigger(StrEnum):
    POLL = "poll"
    # WEBHOOK deferred — the same sync function would handle it as an added
    # trigger source when push is committed (D148, two-threshold rule).
