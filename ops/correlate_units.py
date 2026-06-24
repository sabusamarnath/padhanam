"""Correlate the personal dogfood tenant's work units + goal facets (S66 D168, S67 D169).

The operator-gated trigger for correlation, two steps:

1. **Unit-of-work correlation (D168)** — reads the read-only caches (tasks,
   calendar, email — decrypted on read), runs the title-and-time inference, and
   replaces the tenant's ``:Unit`` / ``:Facet`` / ``SAME_WORK`` subgraph.
2. **Goal-facet correlation (D169)** — reads the units, the goals (with their
   lever-commitment ids), and the commitment names, infers the confidence-tiered
   unit→goal ``SERVES`` edges, and replaces them.

Both are idempotent — re-running recomputes the derived graph from the current
caches + goals (D155). Reads nothing back into any source tool (D166; D167).

Ops-only, composing the daily-driver correlation bridges at the boundary (the
``ops/pull_tasks`` precedent). Must run where the personal-tenant Postgres host
and the shared Neo4j both resolve (inside ``padhanam-api``, via
``make correlate-units``). Run ``make pull-tasks`` (and the calendar/email
refresh) and seed the goals first so the steps have input.
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
        EmailJobSearchSourceAdapter,
        EmailSourceMetadataAdapter,
        FacetSourceAdapter,
        GoalGraphAdapter,
        MatcherQualityRecorderAdapter,
        SuppressionPolicyAdapter,
        UnitGraphAdapter,
    )
    from apps.cli._runtime import build_tenant_wiring
    from contexts.daily_driver.adapters.outbound.postgres.commitment_repository import (  # noqa: E501
        PostgresCommitmentRepository,
    )
    from contexts.daily_driver.application import (
        correlate_goal_facets,
        correlate_units,
    )
    from contexts.ingestion.adapters.outbound.neo4j import (
        Neo4jGraphRepository,
    )
    from padhanam.config import Neo4jSettings
    from shared_kernel import ActorContext, TenantContext, TenantId

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tenant_context: TenantContext = wiring.tenant_context
    session_factory = wiring.session_factory

    async def _session_factory_for_tenant(_tc: TenantContext):
        return session_factory

    async def _resolver(_tid: TenantId):
        return session_factory

    graph = Neo4jGraphRepository.from_settings(Neo4jSettings())
    facet_source = FacetSourceAdapter(
        session_factory_for_tenant=_session_factory_for_tenant
    )
    email_job_search_source = EmailJobSearchSourceAdapter(
        session_factory_for_tenant=_session_factory_for_tenant
    )
    # D209: the source-class taxonomy reads the email sender domain + thread size.
    email_source_metadata = EmailSourceMetadataAdapter(
        session_factory_for_tenant=_session_factory_for_tenant
    )
    # D185/S90: the observe-only matcher-quality recorder — measures the SERVES
    # edges + units each correlate run and persists a quality run (the baseline,
    # then S91's before/after). Edge output is unchanged.
    matcher_quality_recorder = MatcherQualityRecorderAdapter(
        session_factory_for_tenant=_session_factory_for_tenant
    )
    # D186/S91b: read the active matcher policy at the correlate hook. Flag off
    # (the default ship state) → no suppression, identical to the S90 baseline.
    suppression_policy = SuppressionPolicyAdapter(
        session_factory_for_tenant=_session_factory_for_tenant
    )
    unit_graph = UnitGraphAdapter(unit_graph=graph)
    goal_graph = GoalGraphAdapter(outcome_graph=graph)
    commitment_repository = PostgresCommitmentRepository(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
    )

    roles = frozenset({ROLE_OPERATOR})
    actor = ActorContext(
        tenant_context=tenant_context,
        actor_id="ops.correlate_units",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )

    # Step 1 — unit-of-work correlation (D168).
    unit_count = await correlate_units(
        facet_source=facet_source,
        unit_graph=unit_graph,
        actor=actor,
    )
    log.info("unit correlation complete: %d units written", unit_count)

    # Step 2 — goal-facet correlation (D169), over the units just written.
    edge_count = await correlate_goal_facets(
        unit_graph=unit_graph,
        facet_source=facet_source,
        goal_graph=goal_graph,
        commitment_repository=commitment_repository,
        email_job_search_source=email_job_search_source,
        email_source_metadata=email_source_metadata,
        matcher_quality_recorder=matcher_quality_recorder,
        suppression_policy=suppression_policy,
        actor=actor,
    )
    log.info(
        "element-evidence correlation complete: %d EVIDENCES edges written "
        "(D202; goal level derived on read, SERVES retired)",
        edge_count,
    )


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
