"""CalendarRefreshPort — refresh-before-answer seam (D150, P15, S55b-1).

The calendar-conversation cell refreshes the calendar at turn-open before
querying the Meeting store (D150 Option A: always refresh within a tier
budget, fall back to the cached store on miss). The cell depends on this
port; the apps composition root wires it to an adapter driving the D149
`sync_calendar` scoped full pull (commit 4). Keeping the port here means
the cell holds no vendor or pipeline detail — it knows only "refresh, or
tell me you could not."

``refresh`` returns None on success. A refresh that cannot complete
(Nango/Google unreachable, a pipeline error) raises ``CalendarRefreshError``;
the cell catches it (and ``asyncio.TimeoutError`` when the budget is
exceeded) and serves the cached store with a staleness note rather than
failing the turn.
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel.tenant_context import TenantContext


class CalendarRefreshError(Exception):
    """A calendar refresh could not complete; serve the cached store."""


class CalendarRefreshPort(Protocol):
    async def refresh(self, *, tenant_context: TenantContext) -> None:
        """Refresh the tenant's calendar (D149 scoped full pull).

        Returns on a completed refresh. Raises ``CalendarRefreshError`` on
        a refresh that could not complete.
        """
        ...


__all__ = ["CalendarRefreshError", "CalendarRefreshPort"]
