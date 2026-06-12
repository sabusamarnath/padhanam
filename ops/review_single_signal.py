"""Surface the single-signal candidate edges for the ground-truth gate (S91a).

Read-only. Replays the matcher's exact edge computation (the same inputs +
inference + dedup as ``correlate_goal_facets``), filters the single-signal tier
(the weak ``goal-name`` keyword-on-name candidate basis), and writes each as
``(unit_title, matched_goal_name)`` to a **local, gitignored** review artefact so
the operator can confirm each is noise — a cross-goal keyword collision — before
S91b builds the suppression. **No graph write.** The artefact is content (unit
titles, goal names) and never leaves /tmp; only counts go to stdout and the log.

Run inside ``padhanam-api`` (``make review-single-signal``), same host resolution
as ``ops/correlate_units``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

log = logging.getLogger("ops.review_single_signal")

PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"
_REVIEW_DIR = "/tmp/s91_review"
_ARTEFACT = os.path.join(_REVIEW_DIR, "single_signal.tsv")
_JOB_SEARCH_GOAL_NAME = "get a job"


async def _review() -> None:
    from apps.api._daily_driver_wiring import (
        EmailJobSearchSourceAdapter,
        FacetSourceAdapter,
        GoalGraphAdapter,
        UnitGraphAdapter,
    )
    from apps.cli._runtime import build_tenant_wiring
    from contexts.daily_driver.adapters.outbound.postgres.commitment_repository import (  # noqa: E501
        PostgresCommitmentRepository,
    )
    from contexts.daily_driver.domain.goal_assessment import (
        DEFAULT_GOAL_CONFIDENCE_FLOOR,
        WEAK_KEYWORD_BASIS,
        dedup_goal_edges,
        infer_email_job_search_edges,
        infer_goal_edges,
    )
    from contexts.daily_driver.domain.unit_view import build_unit_views
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
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
    unit_graph = UnitGraphAdapter(unit_graph=graph)
    goal_graph = GoalGraphAdapter(outcome_graph=graph)
    commitment_repository = PostgresCommitmentRepository(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
    )
    roles = frozenset({ROLE_OPERATOR})
    actor = ActorContext(
        tenant_context=tenant_context,
        actor_id="ops.review_single_signal",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )

    # Replay the matcher's edge computation (read-only — no replace).
    records = await unit_graph.list_units(tenant_context=tenant_context)
    facets = await facet_source.list_facets(actor=actor)
    views = build_unit_views(
        records, {(f.facet_type, f.facet_id): f for f in facets}
    )
    goals = await goal_graph.list_goals(tenant_context=tenant_context)
    activities = await commitment_repository.list_with_activity(
        tenant_context=tenant_context
    )
    commitment_names = {a.commitment.id: a.commitment.name for a in activities}
    edges = infer_goal_edges(
        views, goals, commitment_names,
        confidence_floor=DEFAULT_GOAL_CONFIDENCE_FLOOR,
    )
    target = next(
        (g for g in goals if g.name.strip().lower() == _JOB_SEARCH_GOAL_NAME),
        None,
    )
    if target is not None:
        confirmed = await email_job_search_source.list_confirmed(actor=actor)
        confirmed_ids = frozenset(c.facet_id for c in confirmed)
        if confirmed_ids:
            edges = dedup_goal_edges(
                edges + infer_email_job_search_edges(views, target.id, confirmed_ids)
            )

    unit_by_id = {v.unit_id: v for v in views}
    goal_by_id = {g.id: g for g in goals}
    single = [e for e in edges if e.basis == WEAK_KEYWORD_BASIS]

    os.makedirs(_REVIEW_DIR, exist_ok=True)
    by_goal: dict[str, int] = {}
    with open(_ARTEFACT, "w") as fh:
        fh.write("unit_title\tmatched_goal\n")
        for e in single:
            unit = unit_by_id.get(e.unit_id)
            goal = goal_by_id.get(e.outcome_id)
            title = unit.title if unit is not None else "(unit not found)"
            goal_name = goal.name if goal is not None else "(goal not found)"
            fh.write(f"{title}\t{goal_name}\n")
            by_goal[goal_name] = by_goal.get(goal_name, 0) + 1

    log.info(
        "single-signal candidates (goal-name keyword-on-name tier): %d",
        len(single),
    )
    # Counts only to stdout — goal names are content, so report the breakdown as
    # a per-goal COUNT without naming goals here (the named detail stays local).
    log.info(
        "spread across %d distinct goals; full (unit, goal) review artefact "
        "(local, gitignored): %s",
        len(by_goal),
        _ARTEFACT,
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("surfacing single-signal candidates for the ground-truth gate (S91a)")
    asyncio.run(_review())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
