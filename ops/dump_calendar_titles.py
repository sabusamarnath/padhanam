"""Dump distinct calendar meeting titles per connection (S78 → S79 seed input).

Reads the personal tenant's meetings through the **decrypting** ``MeetingReader``
(titles are D21 field-encrypted, never read raw), groups them by ``calendar_id``
(= the connection id, D176), and lists each calendar's distinct titles with
frequency, most frequent first. The work calendar's distinct titles are the
lever-name input the S79 professional-goal seed absorbs: a lever-commitment named
to match a recurring work-meeting title fires a confirmed (0.9) SERVES edge
(D169), the gate-relevant coverage; a title too generic to anchor a lever-name
only supports a candidate (0.5) edge.

Read-only. Run after the work-calendar connect + ``make sync-calendar``, inside
``padhanam-api`` via ``make dump-calendar-titles``; capture stdout to the
committed artefact the seed session reads.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections import Counter, defaultdict
from uuid import UUID

import sqlalchemy as sa

log = logging.getLogger("ops.dump_calendar_titles")

PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"


async def _dump() -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.calendar.adapters.outbound.postgres.meeting_store import (
        PostgresMeetingStore,
    )
    from shared_kernel import TenantId

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tenant_context = wiring.tenant_context
    session_factory = wiring.session_factory

    async def _resolver(_tid: TenantId):
        return session_factory

    bound = TenantId(str(tenant_context.tenant_id))

    # Identify which calendar_id is which connection (created_at order: the
    # first is personal, a later one is the work account connected at S78).
    async with session_factory() as session:
        conn_rows = (
            await session.execute(
                sa.text(
                    "SELECT id, left(provider_connection_ref, 12), created_at "
                    "FROM connections WHERE provider = 'google_calendar' "
                    "ORDER BY created_at"
                )
            )
        ).all()
    conn_label = {
        str(r[0]): f"connection {str(r[0])} (ref {r[1]}…, connected {r[2]})"
        for r in conn_rows
    }

    store = PostgresMeetingStore(
        per_tenant_sessionmaker_resolver=_resolver, bound_tenant_id=bound
    )
    meetings = await store.list_meetings(
        tenant_context=tenant_context, include_cancelled=False
    )

    titles_by_cal: dict[str, Counter] = defaultdict(Counter)
    for m in meetings:
        titles_by_cal[m.calendar_id][(m.title or "(untitled)").strip()] += 1

    lines: list[str] = [
        "# Calendar meeting titles per connection (S78 artefact for S79 seed)",
        "",
        f"Tenant {PERSONAL_TENANT_UUID}. {len(meetings)} live meetings across "
        f"{len(titles_by_cal)} calendar(s). Titles read decrypted (D21).",
        "",
    ]
    for cal_id in sorted(
        titles_by_cal, key=lambda c: -sum(titles_by_cal[c].values())
    ):
        counter = titles_by_cal[cal_id]
        label = conn_label.get(cal_id, f"calendar {cal_id} (no connection row)")
        lines.append(f"## {label}")
        lines.append(
            f"{sum(counter.values())} meetings, {len(counter)} distinct titles."
        )
        lines.append("")
        for title, freq in counter.most_common():
            lines.append(f"- ×{freq}  {title}")
        lines.append("")

    sys.stdout.write("\n".join(lines) + "\n")


def main() -> int:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    asyncio.run(_dump())
    return 0


if __name__ == "__main__":
    sys.exit(main())
