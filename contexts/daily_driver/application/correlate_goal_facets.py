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

import logging

from contexts.daily_driver.domain.goal_assessment import (
    DEFAULT_GOAL_CONFIDENCE_FLOOR,
    ElementTarget,
    GoalElementTargets,
    dedup_element_evidence,
    derive_goal_edges,
    element_token_counts,
    infer_element_evidence,
    significant_tokens,
    infer_email_job_search_evidence,
)
from contexts.daily_driver.domain.precision import UnitSource, apply_precision
from contexts.daily_driver.domain.unit_view import build_unit_views
from contexts.daily_driver.domain.work_unit import FacetType
from contexts.daily_driver.ports.commitment_repository import (
    CommitmentRepository,
)
from contexts.daily_driver.ports.email_job_search_source import (
    EmailJobSearchSource,
)
from contexts.daily_driver.ports.email_source_metadata import (
    EmailSourceMetadataSource,
)

_log = logging.getLogger("daily_driver.correlate")
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
    email_source_metadata: EmailSourceMetadataSource | None = None,
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

    # D183/S89: read the rule-confirmed job-search emails once — needed both to
    # protect their units from the precision filter (already-vetted real job work)
    # and to bind them to the outcome below.
    confirmed_ids: frozenset = frozenset()
    if email_job_search_source is not None:
        confirmed = await email_job_search_source.list_confirmed(actor=actor)
        confirmed_ids = frozenset(c.facet_id for c in confirmed)

    # D209: the precision filter — the source-class taxonomy + the genuine-match
    # bar in the use case, gating each lexical candidate before it persists. A
    # board listing routes to market signal, a one-touch ack to pipeline volume,
    # an incidental-token match un-binds, and work no goal genuinely matches parks
    # unbound (coverage honesty at bind time, D171/D193). Protected: units that
    # BELONG_TO a confirmed opportunity (their real work is kept untouched); a
    # confirmed-but-unclustered job email (e.g. a one-touch ack) flows through, so
    # its lexical gate binds route to pipeline while its D183 outcome bind stays.
    # Computed here, not in the matcher domain (D16/D184).
    clustered = await unit_graph.list_clustered_unit_ids(
        tenant_context=actor.tenant_context
    )
    meta_by_facet = {}
    if email_source_metadata is not None:
        for m in await email_source_metadata.list_source_metadata(actor=actor):
            meta_by_facet[m.facet_id] = m
    unit_source: dict = {}
    for v in views:
        present = [f for f in v.facets if f.present]
        email_f = next(
            (f for f in present if f.facet_type is FacetType.EMAIL), None
        )
        if email_f is not None:
            m = meta_by_facet.get(email_f.facet_id)
            unit_source[v.unit_id] = UnitSource(
                facet_type=FacetType.EMAIL,
                domain=m.domain if m else "",
                subject=email_f.title or "",
                thread_size=m.thread_size if m else 1,
                titles=tuple(f.title for f in present if f.title),
            )
        elif present:
            f0 = present[0]
            unit_source[v.unit_id] = UnitSource(
                facet_type=f0.facet_type, domain="", subject=f0.title or "",
                thread_size=1, titles=tuple(f.title for f in present if f.title),
            )
    element_label_by_id = {}
    for gt in targets:
        for el in gt.elements:
            element_label_by_id[el.element_id] = el.label
        if gt.expected_outcome:
            element_label_by_id[gt.outcome_id] = gt.expected_outcome
    tok_counts = element_token_counts(
        tuple(element_label_by_id.values())
    )
    # Corpus token frequency (D209 IDF refinement): how many units contain each
    # significant token, so the bar rejects an element-rare but corpus-common
    # token ("first"/"dose") that floods on its single share.
    unit_token_counts: dict[str, int] = {}
    for v in views:
        seen = set()
        for f in v.facets:
            if f.present and f.title:
                seen |= significant_tokens(f.title)
        for tok in seen:
            unit_token_counts[tok] = unit_token_counts.get(tok, 0) + 1
    precision = apply_precision(
        evidence,
        unit_source=unit_source,
        element_label_by_id=element_label_by_id,
        token_element_counts=tok_counts,
        protected_unit_ids=frozenset(clustered),
        unit_token_counts=unit_token_counts,
    )
    evidence = precision.kept
    _log.info(
        "precision (D209): kept=%d binds; routed market=%d pipeline=%d units; "
        "parked=%d units; protected=%d units",
        len(precision.kept), len(precision.market_units),
        len(precision.pipeline_units), len(precision.parked_units),
        len(precision.protected_units),
    )

    # D183/S89: rule-confirmed job-search emails bind to the Get-a-job outcome
    # element (read back from the persisted store verdict, durable across runs).
    # email-first so its high-specificity basis wins a same-element tie.
    if email_job_search_source is not None and confirmed_ids:
        target = next(
            (g for g in goals if g.name.strip().lower() == _JOB_SEARCH_GOAL_NAME),
            None,
        )
        if target is not None:
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

    # D210: persist the precision pass's disposition counts on the job-search goal
    # so the Map's recommendation-shaped summary reads them (the moat is the
    # confirmed job-email count). Derived state, set each correlate.
    job_goal = next(
        (g for g in goals if g.name.strip().lower() == _JOB_SEARCH_GOAL_NAME), None
    )
    if job_goal is not None:
        await goal_graph.set_disposition_counts(
            tenant_context=actor.tenant_context, outcome_id=job_goal.id,
            moat=len(confirmed_ids), pipeline=len(precision.pipeline_units),
            market=len(precision.market_units), parked=len(precision.parked_units),
        )
    return len(evidence)


__all__ = ["correlate_goal_facets"]
