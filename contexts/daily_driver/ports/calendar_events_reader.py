"""Consumer-defined port for today's calendar events (D159, D17 cross-context seam).

The daily-driver context does not import the calendar context. It declares
the read it needs — the tenant's calendar events for today as the local
``CalendarToday`` projection, each carrying its connection's domain tag —
and an ``apps/`` wiring adapter implements the port by composing the
calendar ``MeetingReader`` and filtering to the current day (the legal
cross-context seam per D17, mirroring ``OpenCasesReader``). Ports layer is
pure per D16.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from contexts.daily_driver.domain.today_item import CalendarToday
from shared_kernel import ActorContext


class CalendarEventsReader(Protocol):
    """Read port returning the actor's calendar events for a day as projections."""

    async def list_today_events(
        self, *, actor: ActorContext, day_date: date
    ) -> tuple[CalendarToday, ...]:
        """Return the tenant's calendar events occurring on ``day_date``."""
        ...


__all__ = ["CalendarEventsReader"]
