"""read_pipeline_stats — the Pipeline stats read (S103q, D217).

A read-and-render projection (S83): joins the goal's ``GoalCddView`` (opportunities
+ gates + the S103i disposition) with the element bindings (each opportunity's
latest activity + touch count, from S103m's ``occurred_at``) and feeds the pure
``build_pipeline_stats``. No graph write; behind ``DAILY_DRIVER_ASSESSMENT_READ``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from contexts.daily_driver.application.read_element_evidence import (
    read_element_bindings,
)
from contexts.daily_driver.domain.pipeline_stats import (
    PipelineOpp,
    PipelineStats,
    build_pipeline_stats,
)
from contexts.daily_driver.ports.facet_source import FacetSource
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from contexts.daily_driver.ports.unit_graph import UnitGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_ASSESSMENT_READ,
    requires_authorisation,
)


def _company_role(name: str) -> tuple[str, str]:
    """Split a "Company — Role" opportunity name; role is empty when absent."""
    if " — " in name:
        company, role = name.split(" — ", 1)
        return company.strip(), role.strip()
    return name.strip(), ""


@requires_authorisation(DAILY_DRIVER_ASSESSMENT_READ)
async def read_pipeline_stats(
    *,
    goal_graph: GoalGraphPort,
    unit_graph: UnitGraphPort,
    facet_source: FacetSource,
    outcome_id: UUID,
    actor: ActorContext,
    now: datetime | None = None,
) -> PipelineStats:
    """Assemble the Pipeline stats for a goal from its CDD view + bindings (D217)."""
    cdd = await goal_graph.read_goal_cdd(
        tenant_context=actor.tenant_context, outcome_id=outcome_id
    )
    bindings = await read_element_bindings(
        unit_graph=unit_graph, facet_source=facet_source,
        goal_graph=goal_graph, actor=actor,
    )
    # Per-opportunity latest activity + distinct touch count, from the bindings.
    units_by_opp: dict[UUID, set[UUID]] = {}
    latest_by_opp: dict[UUID, datetime] = {}
    for b in bindings:
        oid = getattr(b, "opportunity_id", None)
        if oid is None:
            continue
        units_by_opp.setdefault(oid, set()).add(b.unit_id)
        ts = getattr(b, "occurred_at", None)
        if ts is not None and (oid not in latest_by_opp or ts > latest_by_opp[oid]):
            latest_by_opp[oid] = ts

    gate_by_id = {g.gate_id: g for g in cdd.gates}
    opps: list[PipelineOpp] = []
    for o in cdd.opportunities:
        gate = gate_by_id.get(o.current_gate_id)
        company, role = _company_role(o.name)
        opps.append(
            PipelineOpp(
                opportunity_id=o.opportunity_id, company=company, role=role,
                status=o.status, closed_reason=o.closed_reason,
                stage=gate.name if gate is not None else "",
                gate_order=gate.gate_order if gate is not None else None,
                last_activity=latest_by_opp.get(o.opportunity_id),
                touches=len(units_by_opp.get(o.opportunity_id, ())) or o.unit_count,
                fit_tier=o.fit_tier,
                warm_access_available=o.warm_access_available,
                origination_source=o.origination_source,
            )
        )
    one_touch = cdd.disposition.pipeline if cdd.disposition is not None else 0
    return build_pipeline_stats(
        opportunities=tuple(opps),
        one_touch_volume=one_touch,
        now=now or datetime.now(timezone.utc),
    )


__all__ = ["read_pipeline_stats"]
