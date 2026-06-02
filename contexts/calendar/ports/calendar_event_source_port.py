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

D149 (superseding D148's receive-side sync clause): the live S55a smoke
established that a bounded full sync never returns ``nextSyncToken``
(Google emits it only on an *unbounded* sync), so the active pipeline
syncs by scoped full pull on every refresh and ``list_events_incremental``
is **dormant** — built and unit-tested but with no active caller until
the reactivation trigger named in D149 fires.
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
        show_deleted: bool = True,
    ) -> CalendarEventPage:
        """Full sync over a bounded window — the active pipeline path (D149).

        Carries ``timeMin``/``timeMax`` (RFC3339 with offset) and
        ``singleEvents``; never ``syncToken`` or ``q``. With
        ``show_deleted=True`` (the default the pipeline uses), cancelled
        events return with ``status=cancelled`` so the store path can
        tombstone them. ``next_sync_token`` is *not* expected on a bounded
        request (Google emits it only on an unbounded sync); the active
        path neither reads nor writes a sync token.
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

        DORMANT under D149 — present and unit-covered but with no active
        caller, because a bounded full sync never yields a token to seed
        it. ``single_events`` must stay consistent with the full sync that
        issued the token. Raises ``SyncTokenExpiredError`` on HTTP 410.
        Reactivates per the D149 trigger.
        """
        ...
