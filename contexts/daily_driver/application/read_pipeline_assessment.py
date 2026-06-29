"""read_pipeline_assessment — the get-a-job "how am I doing" read (S103p, D216).

A read-and-render projection (S83): reads the goal's ``GoalCddView`` (opportunities
+ gates + the S103i/j disposition block) and feeds the pure ``assess_pipeline``. The
interview gates are those beyond the earliest built gate (apply); the one-touch
volume + activity come from the disposition. No graph write; behind
``DAILY_DRIVER_ASSESSMENT_READ``.
"""

from __future__ import annotations

from uuid import UUID

from contexts.daily_driver.domain.pipeline_assessment import (
    PipelineAssessment,
    assess_pipeline,
)
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_ASSESSMENT_READ,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_ASSESSMENT_READ)
async def read_pipeline_assessment(
    *, goal_graph: GoalGraphPort, outcome_id: UUID, actor: ActorContext
) -> PipelineAssessment:
    """Assess a goal's pipeline from its authored CDD view (D216)."""
    cdd = await goal_graph.read_goal_cdd(
        tenant_context=actor.tenant_context, outcome_id=outcome_id
    )
    gates = cdd.gates
    # "reached interview" = at a gate beyond the earliest built gate (apply).
    min_order = min((g.gate_order for g in gates), default=None)
    interview_gate_ids = frozenset(
        g.gate_id for g in gates
        if min_order is not None and g.gate_order > min_order
    )
    disp = cdd.disposition
    one_touch_volume = disp.pipeline if disp is not None else 0
    activity = disp.moat if disp is not None else 0
    return assess_pipeline(
        opportunities=cdd.opportunities,
        interview_gate_ids=interview_gate_ids,
        one_touch_volume=one_touch_volume,
        activity=activity,
    )


__all__ = ["read_pipeline_assessment"]
