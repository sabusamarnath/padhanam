"""Correlate the personal dogfood tenant's work units (S66, D168).

The operator-gated trigger for unit-of-work correlation: reads the personal
tenant's read-only caches (tasks, calendar, email — decrypted on read), runs the
title-and-time inference, and replaces the tenant's ``:Unit`` / ``:Facet`` /
``SAME_WORK`` subgraph in the shared Neo4j. Idempotent — re-running recomputes
the derived graph from the current caches (D155). Reads nothing back into any
source tool (D166; the caches are read-only, D167).

Ops-only, composing the daily-driver correlation bridges at the boundary (the
``ops/pull_tasks`` precedent). Must run where the personal-tenant Postgres host
and the shared Neo4j both resolve (inside ``padhanam-api``, via
``make correlate-units``). Run ``make pull-tasks`` (and the calendar/email
refresh) first so the caches are populated.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from shared_kernel.authorisation import (
    ROLE_OPERATOR,
    authorisations_for_roles,
)

log = logging.getLogger("ops.correlate_units")

# Personal dogfood tenant (ops/dogfood_provision.py).
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"


async def _correlate() -> None:
    from apps.api._daily_driver_wiring import (
        FacetSourceAdapter,
        UnitGraphAdapter,
    )
    from apps.cli._runtime import build_tenant_wiring
    from contexts.daily_driver.application import correlate_units
    from contexts.ingestion.adapters.outbound.neo4j import (
        Neo4jGraphRepository,
    )
    from padhanam.config import Neo4jSettings
    from shared_kernel import ActorContext, TenantContext

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tenant_context: TenantContext = wiring.tenant_context
    session_factory = wiring.session_factory

    async def _session_factory_for_tenant(_tc: TenantContext):
        return session_factory

    facet_source = FacetSourceAdapter(
        session_factory_for_tenant=_session_factory_for_tenant
    )
    unit_graph = UnitGraphAdapter(
        unit_graph=Neo4jGraphRepository.from_settings(Neo4jSettings())
    )

    roles = frozenset({ROLE_OPERATOR})
    actor = ActorContext(
        tenant_context=tenant_context,
        actor_id="ops.correlate_units",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )

    count = await correlate_units(
        facet_source=facet_source,
        unit_graph=unit_graph,
        actor=actor,
    )
    log.info("correlation complete: %d units written", count)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("correlating work units for the personal dogfood tenant (S66)")
    asyncio.run(_correlate())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
