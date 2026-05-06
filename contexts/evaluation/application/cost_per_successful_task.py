"""cost_per_successful_task use case (D8, D49, D57, S17b).

The substantive eval-harness deliverable for S17b. Computes
cost-per-successful-task as a single rollup over a scoring-sheet
revision applied to an interaction set, joining rubric_applications
by trace_id to the trace store's gen_ai.cost.* attributes per D49
through evaluation's CostQueryPort (D57 two-layer abstraction).

Algorithm:

1. Load every rubric_application persisted for (revision_id,
   interaction_set_id) via the repository port.
2. Load every (criterion, applier_config) pair on the revision via
   the scoring-sheet repository port; index criteria by id.
3. For each rubric_application, look up the criterion that owns it
   and find the level entry whose ``label`` matches the
   ``automated_score``. Read the level's ``is_success`` flag.
4. Filter to the successful set: applications whose label matched
   AND whose level's ``is_success`` is True.
5. Collect unique trace_ids from the successful set (excluding
   None and empty-string trace_ids — both indicate the
   rubric_application was produced by a path that did not pass
   through the replay engine, per S17a's empty-string-to-NULL
   convention).
6. Query CostQueryPort.get_costs_by_trace_ids for the unique trace
   ids; the port returns a dict that is absent for traces without
   cost data, cross-tenant traces, or 404s.
7. Sum costs across the unique trace_ids that returned data; this
   is total_cost_usd (deduplicated per inference call — multiple
   criteria on the same model output share one trace_id and one
   inference cost).
8. Compute cost_per_task_usd = total_cost_usd / successful_count
   where successful_count is the number of successful
   rubric_applications (not the number of unique trace_ids; the
   metric's denominator is "successful task observations" which
   includes multiple criteria-applications per output).
9. Compute excluded_count: count of successful rubric_applications
   that did not contribute to the cost rollup (no trace_id, or
   trace_id present but absent from the cost result).

The reflection-prompt 3 framing in the S17b session log discusses
the design choice: the divisor is the full successful_count and
``excluded_count`` is the diagnostic. A consumer reading
``cost_per_task_usd`` alongside ``excluded_count`` distinguishes
"low cost-per-task because the model is cheap" from "low
cost-per-task because most successful applications could not be
costed".

Per-criterion cost breakdowns are P11 territory; this use case
returns one rollup across heterogeneous criteria. The recommendation
engine consumes per-criterion data when it lands.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from contexts.evaluation.domain.cost_per_successful_task_result import (
    CostPerSuccessfulTaskResult,
)
from contexts.evaluation.domain.scoring_sheet import Criterion
from contexts.evaluation.ports.cost_query_port import CostQueryPort
from contexts.evaluation.ports.rubric_application_repository_port import (
    RubricApplicationRepositoryPort,
)
from contexts.evaluation.ports.scoring_sheet_repository_port import (
    ScoringSheetRepositoryPort,
)
from shared_kernel import TenantContext


async def cost_per_successful_task(
    *,
    tenant_context: TenantContext,
    scoring_sheet_revision_id: UUID,
    interaction_set_id: UUID,
    scoring_sheet_repository: ScoringSheetRepositoryPort,
    rubric_application_repository: RubricApplicationRepositoryPort,
    cost_query_port: CostQueryPort,
) -> CostPerSuccessfulTaskResult:
    rubric_apps = await rubric_application_repository.list_for_revision_and_set(
        scoring_sheet_revision_id=scoring_sheet_revision_id,
        interaction_set_id=interaction_set_id,
    )
    if not rubric_apps:
        return CostPerSuccessfulTaskResult(
            total_cost_usd=Decimal("0"),
            successful_count=0,
            cost_per_task_usd=Decimal("0"),
            excluded_count=0,
        )

    pairs = await scoring_sheet_repository.get_criteria_with_appliers(
        scoring_sheet_revision_id
    )
    criteria_by_id: dict[UUID, Criterion] = {
        criterion.id: criterion for criterion, _ in pairs
    }

    successful_apps = []
    for app in rubric_apps:
        criterion = criteria_by_id.get(app.criterion_id)
        if criterion is None:
            # Defensive: revision's criteria set should cover every
            # rubric_application via FK; a missing criterion is data
            # drift, not a normal path. Skip rather than crash; the
            # row is excluded from both numerator and denominator.
            continue
        if app.automated_score is None:
            continue
        for level in criterion.levels:
            if level.label == app.automated_score:
                if level.is_success:
                    successful_apps.append(app)
                break

    successful_count = len(successful_apps)
    if successful_count == 0:
        return CostPerSuccessfulTaskResult(
            total_cost_usd=Decimal("0"),
            successful_count=0,
            cost_per_task_usd=Decimal("0"),
            excluded_count=0,
        )

    unique_trace_ids = sorted(
        {
            app.trace_id
            for app in successful_apps
            if app.trace_id  # excludes None and ""; per S17a convention
        }
    )

    if unique_trace_ids:
        costs = await cost_query_port.get_costs_by_trace_ids(
            unique_trace_ids, tenant_context
        )
    else:
        costs = {}

    total_cost = Decimal("0")
    for trace_id, breakdown in costs.items():
        total_cost += breakdown.total_usd

    excluded = sum(
        1
        for app in successful_apps
        if not app.trace_id or app.trace_id not in costs
    )

    cost_per_task = (
        total_cost / successful_count if successful_count > 0 else Decimal("0")
    )

    return CostPerSuccessfulTaskResult(
        total_cost_usd=total_cost,
        successful_count=successful_count,
        cost_per_task_usd=cost_per_task,
        excluded_count=excluded,
    )
