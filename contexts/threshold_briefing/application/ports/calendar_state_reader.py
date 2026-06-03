"""CalendarStateReader consumer port (D153, S57).

The threshold-evaluator's cross-context read surface over the calendar
*state* store. Per D153's reconciliation correction the evaluator reads
current calendar state (the meetings store), not the audit chain — so
this port returns the current meetings, including cancelled ones (the
cancellation rule needs the tombstones; the conflict rule needs the
confirmed set).

Per the consumer-port-returns-local-DTO discipline (D146; mirroring
DailyBriefingReader), this port returns the threshold-owned domain
``MeetingState`` projection, not the calendar domain ``Meeting`` type —
so the threshold context never imports the calendar context. The
``apps/`` wiring adapter maps calendar ``Meeting`` → ``MeetingState``.

Framework-free per D16 — stdlib plus shared_kernel only.
"""

from __future__ import annotations

from typing import Protocol

from contexts.threshold_briefing.domain.meeting_state import MeetingState
from shared_kernel import ActorContext


class CalendarStateReader(Protocol):
    """Read-side consumer port over the calendar state store (D153)."""

    async def list_meetings(
        self, *, actor: ActorContext, include_cancelled: bool = True
    ) -> tuple[MeetingState, ...]:
        """Return the tenant's current stored meetings as state projections.

        Includes cancelled meetings by default (the cancellation rule
        matches over tombstones whose ``cancelled_at`` falls in the scan
        window). The wiring adapter delegates to the calendar
        ``MeetingReader.list_meetings`` and maps each ``Meeting`` to a
        ``MeetingState``.
        """
        ...


__all__ = ["CalendarStateReader", "MeetingState"]
