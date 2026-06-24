"""correlate_goal_facets use case — bind units to authored elements (D202, S103b).

The second correlation step (after ``correlate_units`` builds the unit graph):
reads the units (enriched with their cache facet titles), the goals, and each
goal's authored CDD elements, binds each unit to the nearest authored element(s)
*within* its goal via lexical-and-alias recall (multi-attach), and writes the
**element evidence** through the ``UnitGraphPort`` — the goal-level ``SERVES``
write is retired (the goal level derives on read, D202). A unit matching no
element parks unbound (no edge), the emergent loop's queue (S104). Derived state
(D155), idempotent. Never writes back to any source tool (D166).

No direction this session (S104, D203); no embedding tier (S100 empty corpus).
"""

from __future__ import annotations

from contexts.daily_driver.domain.goal_assessment import (
    DEFAULT_GOAL_CONFIDENCE_FLOOR,
    ElementTarget,
    GoalElementTargets,
    dedup_element_evidence,
    derive_goal_edges,
    infer_element_evidence,
    infer_email_job_search_evidence,
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
from contexts.daily_driver.ports.suppression_policy import SuppressionPolicy
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
    suppression_policy: SuppressionPolicy | None = None,
    confidence_floor: float = DEFAULT_GOAL_CONFIDENCE_FLOOR,
) -> int:
    """Recompute and persist the tenant's unit→element evidence. Returns edge count.

    ``commitment_repository`` and ``confidence_floor`` are retained for signature
    stability (the wiring + the goal-level floor); the element matcher binds to the
    authored element labels, not the commitment names.
    """
    records = await unit_graph.list_units(tenant_context=actor.tenant_context)
    facets = await facet_source.list_facets(actor=actor)
    views = build_unit_views(
        records, {(f.facet_type, f.facet_id): f for f in facets}
    )
    # D203/S103c: the re-match is correction-respecting — a unit the user has
    # corrected (user-owned) is skipped entirely, so its bindings are never
    # re-derived or overwritten. The replace deletes only non-user-owned
    # EVIDENCES, so this filter and the delete agree on the same set.
    user_owned = await unit_graph.list_user_owned_unit_ids(
        tenant_context=actor.tenant_context
    )
    if user_owned:
        views = tuple(v for v in views if v.unit_id not in user_owned)
    goals = await goal_graph.list_goals(tenant_context=actor.tenant_context)

    # Each goal's authored CDD elements become the per-element match targets.
    targets: list[GoalElementTargets] = []
    for goal in goals:
        cdd = await goal_graph.read_goal_cdd(
            tenant_context=actor.tenant_context, outcome_id=goal.id
        )
        elements = tuple(
            ElementTarget(
                kind=e.kind.value, element_id=e.element_id, label=e.label,
                gate_id=e.gate_id,
            )
            for e in cdd.elements
        )
        targets.append(
            GoalElementTargets(
                outcome_id=goal.id,
                name=goal.name,
                aliases=tuple(goal.aliases),
                elements=elements,
                expected_outcome=cdd.expected_outcome,
            )
        )

    evidence = infer_element_evidence(views, tuple(targets))

    # D183/S89: rule-confirmed job-search emails bind to the Get-a-job outcome
    # element (read back from the persisted store verdict, durable across runs).
    # email-first so its high-specificity basis wins a same-element tie.
    if email_job_search_source is not None:
        target = next(
            (g for g in goals if g.name.strip().lower() == _JOB_SEARCH_GOAL_NAME),
            None,
        )
        if target is not None:
            confirmed = await email_job_search_source.list_confirmed(actor=actor)
            confirmed_ids = frozenset(c.facet_id for c in confirmed)
            if confirmed_ids:
                email_ev = infer_email_job_search_evidence(
                    views, target.id, confirmed_ids
                )
                evidence = dedup_element_evidence(list(email_ev) + list(evidence))

    # D186/S91b: when single-signal suppression is active, drop the weak alias-tier
    # evidence (the goal-name keyword analog) — an applied recommendation re-applied
    # every run (D155), not a per-item edit. Flag off leaves the set unchanged.
    if suppression_policy is not None and await suppression_policy.suppress_single_signal(
        actor=actor
    ):
        evidence = tuple(e for e in evidence if e.tier != "alias")

    # D185/S90: observe-only matcher-quality hook measures the derived goal-level
    # rollup (the producer stays goal-shaped), before the write so it reads exactly
    # what lands. Default-None keeps correlation unchanged when not wired.
    if matcher_quality_recorder is not None:
        await matcher_quality_recorder.record(
            actor=actor, edges=derive_goal_edges(evidence), units=views
        )

    await unit_graph.replace_element_evidence(
        tenant_context=actor.tenant_context, evidence=evidence
    )
    return len(evidence)


__all__ = ["correlate_goal_facets"]
