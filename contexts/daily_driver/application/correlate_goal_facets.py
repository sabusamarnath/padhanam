"""correlate_goal_facets use case — infer + persist the unit→goal facet (D169).

The second correlation step (after ``correlate_units`` builds the unit graph):
reads the units (enriched with their cache facet titles), the goals (with their
lever-commitment ids), and the commitment names, runs the confidence-tiered
``infer_goal_edges`` inference, and replaces the tenant's ``SERVES`` edges
through the ``UnitGraphPort``. Derived state (D155), idempotent. Never writes
back to any source tool — the goal facet is Padhanam-native (D166).
"""

from __future__ import annotations

from contexts.daily_driver.domain.goal_assessment import (
    DEFAULT_GOAL_CONFIDENCE_FLOOR,
    dedup_goal_edges,
    infer_email_job_search_edges,
    infer_goal_edges,
)
from contexts.daily_driver.domain.unit_view import build_unit_views
from contexts.daily_driver.ports.commitment_repository import (
    CommitmentRepository,
)
from contexts.daily_driver.ports.email_job_search_source import (
    EmailJobSearchSource,
)
from contexts.daily_driver.ports.facet_source import FacetSource
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from contexts.daily_driver.ports.matcher_quality_recorder import (
    MatcherQualityRecorder,
)
from contexts.daily_driver.ports.unit_graph import UnitGraphPort

# The job-search emails serve this goal (D183). Named match against the seeded
# Get-a-job outcome; a goal-level "this is the job-search goal" flag is the
# general form, deferred (one dogfood instance).
_JOB_SEARCH_GOAL_NAME = "get a job"
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_UNITS_CORRELATE,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_UNITS_CORRELATE)
async def correlate_goal_facets(
    *,
    unit_graph: UnitGraphPort,
    facet_source: FacetSource,
    goal_graph: GoalGraphPort,
    commitment_repository: CommitmentRepository,
    actor: ActorContext,
    email_job_search_source: EmailJobSearchSource | None = None,
    matcher_quality_recorder: MatcherQualityRecorder | None = None,
    confidence_floor: float = DEFAULT_GOAL_CONFIDENCE_FLOOR,
) -> int:
    """Recompute and persist the tenant's unit→goal facet. Returns edge count."""
    records = await unit_graph.list_units(tenant_context=actor.tenant_context)
    facets = await facet_source.list_facets(actor=actor)
    views = build_unit_views(
        records, {(f.facet_type, f.facet_id): f for f in facets}
    )
    goals = await goal_graph.list_goals(tenant_context=actor.tenant_context)
    activities = await commitment_repository.list_with_activity(
        tenant_context=actor.tenant_context
    )
    commitment_names = {
        a.commitment.id: a.commitment.name for a in activities
    }
    edges = infer_goal_edges(
        views, goals, commitment_names, confidence_floor=confidence_floor
    )
    # D183/S89: the classifier-fed edge. Rule-confirmed job-search emails (read
    # back from the persisted store verdict, so durable across recomputes) serve
    # the Get-a-job outcome at high confidence; unioned + deduped with the
    # title-match edges, the rule basis winning the tiebreak.
    if email_job_search_source is not None:
        target = next(
            (g for g in goals if g.name.strip().lower() == _JOB_SEARCH_GOAL_NAME),
            None,
        )
        if target is not None:
            confirmed = await email_job_search_source.list_confirmed(actor=actor)
            confirmed_ids = frozenset(c.facet_id for c in confirmed)
            if confirmed_ids:
                email_edges = infer_email_job_search_edges(
                    views, target.id, confirmed_ids
                )
                edges = dedup_goal_edges(edges + email_edges)
    # D185/S90: observe-only matcher-quality hook. The recorder measures the
    # final edge set + units and persists a quality run; it must not mutate the
    # edges. Placed before the replace so the measurement is exactly what gets
    # written. Default-None keeps correlation unchanged when not wired.
    if matcher_quality_recorder is not None:
        await matcher_quality_recorder.record(
            actor=actor, edges=edges, units=views
        )
    await unit_graph.replace_goal_edges(
        tenant_context=actor.tenant_context, edges=edges
    )
    return len(edges)


__all__ = ["correlate_goal_facets"]
