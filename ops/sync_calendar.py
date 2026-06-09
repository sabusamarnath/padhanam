"""Re-pull the personal dogfood tenant's calendar (D159 deployment smoke).

The operator-gated live trigger for a calendar re-pull, mirroring
``ops/pull_tasks`` and ``ops/correlate_units``. Resolves the personal tenant's
``google_calendar`` connection and drives the D150 refresh adapter (the
``_default_first_sync`` path in ``apps/api/_calendar_connect_wiring``), which
runs the D149 scoped full pull (``sync_calendar``) against the live Nango Proxy
into the re-pullable ``meetings`` cache (D155). Read-only — pulls and upserts the
cache, writes nothing back to Google.

Added at the D159 deployment close so the post-migration smoke is a repeatable
scripted artifact rather than a UI action, and so the work-calendar connect that
follows can re-run it. Ops-only, composing the calendar refresh adapter at the
boundary; must run where the personal-tenant Postgres host resolves and Nango is
reachable (inside ``padhanam-api``, via ``make sync-calendar``).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from uuid import UUID

import sqlalchemy as sa

log = logging.getLogger("ops.sync_calendar")

# Personal dogfood tenant (ops/dogfood_provision.py).
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"


async def _sync() -> None:
    from apps.cli._calendar import build_calendar_refresh_adapter
    from apps.cli._runtime import build_tenant_wiring

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tenant_context = wiring.tenant_context
    session_factory = wiring.session_factory

    # Resolve the personal tenant's google_calendar connection id (created at
    # connect time with a non-deterministic uuid, so it is read, not assumed).
    async with session_factory() as session:
        row = (
            await session.execute(
                sa.text(
                    "SELECT id FROM connections "
                    "WHERE provider = 'google_calendar' "
                    "ORDER BY created_at LIMIT 1"
                )
            )
        ).first()
    if row is None:
        raise SystemExit(
            "no google_calendar connection for the personal tenant — connect "
            "the calendar before re-pulling."
        )
    connection_id = UUID(str(row[0]))
    log.info("resolved google_calendar connection %s", connection_id)

    adapter = build_calendar_refresh_adapter(
        tenant_id=PERSONAL_TENANT_UUID, connection_id=connection_id
    )
    result = await adapter.refresh(tenant_context=tenant_context)
    log.info("calendar re-pull complete: %r", result)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("re-pulling the calendar for the personal dogfood tenant")
    asyncio.run(_sync())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
