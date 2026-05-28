"""CalendarEventSourcePort — the outbound port the pull pipeline depends on (D148).

The port exists for hexagonal layering (the application cannot import
adapters), implemented by exactly one adapter this phase
(``NangoProxyCalendarAdapter``). It is not a vendor-abstraction layer
justified by an anticipated second provider — the two-threshold rule's
tell returns *wait* until a second adapter is structurally guaranteed;
replaceability is secured by the Connection model and self-hosting, not
by a premature second adapter.

Full and incremental sync are two distinct methods because the Google
``events.list`` API makes ``syncToken`` mutually exclusive with
``timeMin``/``timeMax``/``q``/``orderBy``/``updatedMin`` (passing them
together returns 400). Encoding the two as separate methods makes the
vendor constraint structural rather than a call-site discipline: the
window is set on the full sync; incremental sync carries only the sync
token.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from contexts.calendar.domain.calendar_event import CalendarEventPage
from contexts.calendar.domain.connection import Connection


class CalendarEventSourcePort(Protocol):
    async def list_events_full(
        self,
        *,
        connection: Connection,
        time_min: datetime,
        time_max: datetime,
        page_token: str | None = None,
        calendar_id: str = "primary",
        single_events: bool = True,
    ) -> CalendarEventPage:
        """Full/initial sync over a bounded window.

        Carries ``timeMin``/``timeMax`` (RFC3339 with offset) and
        ``singleEvents``; never ``syncToken`` or ``q``. The final page
        carries ``next_sync_token`` for subsequent incremental pulls.
        """
        ...

    async def list_events_incremental(
        self,
        *,
        connection: Connection,
        sync_token: str,
        page_token: str | None = None,
        calendar_id: str = "primary",
        single_events: bool = True,
    ) -> CalendarEventPage:
        """Incremental sync carrying only the sync token (plus pagination).

        ``single_events`` must stay consistent with the full sync that
        issued the token. Raises ``SyncTokenExpiredError`` on HTTP 410,
        which the pipeline answers with a full resync.
        """
        ...
