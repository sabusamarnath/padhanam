"""Measure the matcher's no-clear-basis bindings (S103d, D204).

Reads the live element-evidence bindings through the same read path the surface
uses (``read_element_bindings``), recomputes each binding's *why* via
``binding_rationale``, and reports how many bindings the read side calls
``NO_CLEAR_BASIS`` — broken down by tier — plus the bound-unit count.

The S103d before/after measure: before the substring-branch drop the alias tier
carries the baseless binds; after a re-correlate on the tightened matcher the
count is zero and the bound-unit count falls by exactly the removed set. Reports
ids only (unit / element / outcome), never titles or content (D21).

Ops-only, wired like ``ops/correlate_units``. Run inside ``padhanam-api``.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from shared_kernel.authorisation import (
    ROLE_OPERATOR,
    authorisations_for_roles,
)

log = logging.getLogger("ops.measure_alias_basis")

PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"


async def _measure() -> None:
    from apps.api._daily_driver_wiring import (
        FacetSourceAdapter,
        GoalGraphAdapter,
        UnitGraphAdapter,
    )
    from apps.cli._runtime import build_tenant_wiring
    from contexts.daily_driver.application.read_element_evidence import (
        read_element_bindings,
    )
    from contexts.daily_driver.domain.goal_assessment import NO_CLEAR_BASIS
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

    graph = Neo4jGraphRepository.from_settings(Neo4jSettings())
    facet_source = FacetSourceAdapter(
        session_factory_for_tenant=_session_factory_for_tenant
    )
    unit_graph = UnitGraphAdapter(unit_graph=graph)
    goal_graph = GoalGraphAdapter(outcome_graph=graph)

    roles = frozenset({ROLE_OPERATOR})
    actor = ActorContext(
        tenant_context=tenant_context,
        actor_id="ops.measure_alias_basis",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )

    bindings = await read_element_bindings(
        unit_graph=unit_graph,
        facet_source=facet_source,
        goal_graph=goal_graph,
        actor=actor,
    )

    bound_units = {b.unit_id for b in bindings}
    baseless = [b for b in bindings if b.matched_term == NO_CLEAR_BASIS]
    by_tier: dict[str, int] = {}
    for b in baseless:
        by_tier[b.tier] = by_tier.get(b.tier, 0) + 1

    log.info("total bindings: %d", len(bindings))
    log.info("bound units: %d", len(bound_units))
    log.info("no-clear-basis bindings: %d", len(baseless))
    log.info("no-clear-basis by tier: %s", dict(sorted(by_tier.items())))
    for b in baseless:
        # ids only (D21): no titles, no content.
        log.info(
            "  baseless: tier=%s unit=%s element=%s outcome=%s",
            b.tier, b.unit_id, b.element_id, b.outcome_id,
        )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    asyncio.run(_measure())
    return 0


if __name__ == "__main__":
    sys.exit(main())
