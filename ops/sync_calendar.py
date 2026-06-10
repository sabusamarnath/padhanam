"""Re-pull the personal dogfood tenant's calendar(s) (D159/D176 deployment + connect).

The operator-gated live trigger for a calendar re-pull, mirroring
``ops/pull_tasks`` and ``ops/correlate_units``. Resolves **every**
``google_calendar`` connection on the tenant (D176 permits a second account as a
distinct connection row) and drives the D150 refresh adapter per connection — the
D149 scoped full pull (``sync_calendar``) against the live Nango Proxy into the
re-pullable ``meetings`` cache (D155). Each pull is scoped by ``calendar_id`` (=
the connection id, D176), so a pull of one calendar never overwrites, tombstones,
or ages out another calendar's rows.

Read-only — pulls and upserts the cache, writes nothing back to Google. Added at
the D159 deployment close (S77) and extended to multi-connection at the
work-calendar connect (S78). Ops-only; must run where the personal-tenant
Postgres host resolves and Nango is reachable (inside ``padhanam-api``, via
``make sync-calendar``).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Callable, Protocol
from uuid import UUID

import sqlalchemy as sa

log = logging.getLogger("ops.sync_calendar")

# Personal dogfood tenant (ops/dogfood_provision.py).
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"


class _RefreshAdapter(Protocol):
    async def refresh(self, *, tenant_context: object) -> object: ...


# build_calendar_refresh_adapter(tenant_id=..., connection_id=...) -> adapter.
AdapterBuilder = Callable[..., _RefreshAdapter]


async def sync_all_connections(
    *,
    tenant_id: str,
    tenant_context: object,
    connection_ids: list[UUID],
    build_adapter: AdapterBuilder,
) -> list[tuple[UUID, object]]:
    """Refresh every connection, each scoped by its own ``calendar_id`` (D176).

    Builds the refresh adapter per connection id and refreshes it; because
    ``build_calendar_refresh_adapter`` drives ``sync_calendar`` with that
    connection id, every Meeting it writes is stamped and scoped by
    ``calendar_id = str(connection_id)`` — so one calendar's pull never
    cross-writes another's rows. Returns ``(connection_id, result)`` per
    connection for logging.
    """
    results: list[tuple[UUID, object]] = []
    for connection_id in connection_ids:
        adapter = build_adapter(tenant_id=tenant_id, connection_id=connection_id)
        result = await adapter.refresh(tenant_context=tenant_context)
        results.append((connection_id, result))
    return results


async def _resolve_connection_ids(session_factory: Callable[[], object]) -> list[UUID]:
    """Read every google_calendar connection id for the bound tenant (oldest first)."""
    async with session_factory() as session:  # type: ignore[attr-defined]
        rows = (
            await session.execute(
                sa.text(
                    "SELECT id FROM connections "
                    "WHERE provider = 'google_calendar' "
                    "ORDER BY created_at"
                )
            )
        ).all()
    return [UUID(str(r[0])) for r in rows]


async def _sync() -> None:
    from apps.cli._calendar import build_calendar_refresh_adapter
    from apps.cli._runtime import build_tenant_wiring

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tenant_context = wiring.tenant_context
    session_factory = wiring.session_factory

    connection_ids = await _resolve_connection_ids(session_factory)
    if not connection_ids:
        raise SystemExit(
            "no google_calendar connection for the personal tenant — connect "
            "the calendar before re-pulling."
        )
    log.info(
        "resolved %d google_calendar connection(s): %s",
        len(connection_ids),
        ", ".join(str(c) for c in connection_ids),
    )

    results = await sync_all_connections(
        tenant_id=PERSONAL_TENANT_UUID,
        tenant_context=tenant_context,
        connection_ids=connection_ids,
        build_adapter=build_calendar_refresh_adapter,
    )
    for connection_id, result in results:
        log.info("calendar %s re-pull complete: %r", connection_id, result)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("re-pulling all calendars for the personal dogfood tenant")
    asyncio.run(_sync())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
