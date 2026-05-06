"""compare_runs use case (D58, S18).

Compares two runs of a scoring sheet (a baseline revision and a
candidate revision) against the same interaction set. Produces a
``RegressionReport`` with per-criterion success-rate deltas and
aggregate metrics including cost-per-task on each side.

Algorithm:

1. Load every rubric_application persisted for the baseline
   ``(revision_id, interaction_set_id)`` pair via the repository.
2. Same for the candidate revision.
3. Load every ``(criterion, applier_config)`` pair on each revision
   via the scoring-sheet repository.
4. Index criteria by ``name`` on each side (criterion ids differ
   across revisions because each revision creates fresh criterion
   rows; the human-stable identity is the criterion name).
5. For each criterion name in the union of (baseline_names,
   candidate_names), compute success-rate on each side and the
   delta. ``CriterionDelta`` carries baseline_count and
   candidate_count so consumers can distinguish "no data" from
   "all failures."
6. Compute aggregate counts (total applications, total successful)
   on each side.
7. Call ``cost_per_successful_task`` for each side to get the
   cost-per-task. The use case is reused unchanged; the comparison
   is the new top-level orchestrator that runs it twice.
8. Construct the ``RegressionReport`` with per-criterion deltas,
   aggregate metrics, and ``generated_at`` set to the current UTC
   timestamp.

The success-detection logic mirrors ``cost_per_successful_task``
(matching automated_score against criterion levels and reading
``is_success``). The repeated logic is acceptable at two callers
with the same semantics; if a third consumer arrives, promotion to
a shared helper inside the application layer is the right move.

The use case is async because every port it consumes is async;
two cost queries run sequentially rather than concurrently. Future
refinement could ``asyncio.gather`` them, but at single-tenant
scale the latency cost is small and concurrent cost queries
compete for the Langfuse worker pool — the simpler shape is
honest.

D17 facade: external consumers (the CLI runner at S18, the P11
recommendation engine) call this through ``contexts/evaluation/``'s
implicit api surface. There is no separate ``api.py`` for evaluation
at S18 because no cross-context import target exists yet — the CLI
calls the application layer directly through composition wiring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from contexts.evaluation.application.cost_per_successful_task import (
    cost_per_successful_task,
)
from contexts.evaluation.domain.regression_report import (
    AggregateMetrics,
    CriterionDelta,
    RegressionReport,
)
from contexts.evaluation.domain.rubric_application import RubricApplication
from contexts.evaluation.domain.scoring_sheet import Criterion
from contexts.evaluation.ports.cost_query_port import CostQueryPort
from contexts.evaluation.ports.rubric_application_repository_port import (
    RubricApplicationRepositoryPort,
)
from contexts.evaluation.ports.scoring_sheet_repository_port import (
    ScoringSheetRepositoryPort,
)
from shared_kernel import TenantContext


async def compare_runs(
    *,
    tenant_context: TenantContext,
    baseline_revision_id: UUID,
    candidate_revision_id: UUID,
    interaction_set_id: UUID,
    scoring_sheet_repository: ScoringSheetRepositoryPort,
    rubric_application_repository: RubricApplicationRepositoryPort,
    cost_query_port: CostQueryPort,
) -> RegressionReport:
    baseline_apps = await rubric_application_repository.list_for_revision_and_set(
        scoring_sheet_revision_id=baseline_revision_id,
        interaction_set_id=interaction_set_id,
    )
    candidate_apps = await rubric_application_repository.list_for_revision_and_set(
        scoring_sheet_revision_id=candidate_revision_id,
        interaction_set_id=interaction_set_id,
    )

    baseline_pairs = await scoring_sheet_repository.get_criteria_with_appliers(
        baseline_revision_id
    )
    candidate_pairs = await scoring_sheet_repository.get_criteria_with_appliers(
        candidate_revision_id
    )
    baseline_criteria_by_id: dict[UUID, Criterion] = {
        criterion.id: criterion for criterion, _ in baseline_pairs
    }
    candidate_criteria_by_id: dict[UUID, Criterion] = {
        criterion.id: criterion for criterion, _ in candidate_pairs
    }
    baseline_criteria_by_name: dict[str, Criterion] = {
        criterion.name: criterion for criterion, _ in baseline_pairs
    }
    candidate_criteria_by_name: dict[str, Criterion] = {
        criterion.name: criterion for criterion, _ in candidate_pairs
    }

    per_criterion_deltas = _compute_criterion_deltas(
        baseline_apps=baseline_apps,
        candidate_apps=candidate_apps,
        baseline_criteria_by_id=baseline_criteria_by_id,
        candidate_criteria_by_id=candidate_criteria_by_id,
        baseline_criteria_by_name=baseline_criteria_by_name,
        candidate_criteria_by_name=candidate_criteria_by_name,
    )

    baseline_successful = _count_successful(
        baseline_apps, baseline_criteria_by_id
    )
    candidate_successful = _count_successful(
        candidate_apps, candidate_criteria_by_id
    )

    baseline_cost = await cost_per_successful_task(
        tenant_context=tenant_context,
        scoring_sheet_revision_id=baseline_revision_id,
        interaction_set_id=interaction_set_id,
        scoring_sheet_repository=scoring_sheet_repository,
        rubric_application_repository=rubric_application_repository,
        cost_query_port=cost_query_port,
    )
    candidate_cost = await cost_per_successful_task(
        tenant_context=tenant_context,
        scoring_sheet_revision_id=candidate_revision_id,
        interaction_set_id=interaction_set_id,
        scoring_sheet_repository=scoring_sheet_repository,
        rubric_application_repository=rubric_application_repository,
        cost_query_port=cost_query_port,
    )

    baseline_rate = (
        baseline_successful / len(baseline_apps) if baseline_apps else 0.0
    )
    candidate_rate = (
        candidate_successful / len(candidate_apps) if candidate_apps else 0.0
    )

    aggregate_metrics = AggregateMetrics(
        total_baseline_applications=len(baseline_apps),
        total_candidate_applications=len(candidate_apps),
        total_baseline_successful=baseline_successful,
        total_candidate_successful=candidate_successful,
        overall_baseline_success_rate=baseline_rate,
        overall_candidate_success_rate=candidate_rate,
        overall_success_rate_delta=candidate_rate - baseline_rate,
        baseline_cost_per_task_usd=baseline_cost.cost_per_task_usd,
        candidate_cost_per_task_usd=candidate_cost.cost_per_task_usd,
        overall_cost_per_task_delta_usd=(
            candidate_cost.cost_per_task_usd - baseline_cost.cost_per_task_usd
        ),
    )

    return RegressionReport(
        baseline_revision_id=baseline_revision_id,
        candidate_revision_id=candidate_revision_id,
        interaction_set_id=interaction_set_id,
        per_criterion_deltas=tuple(per_criterion_deltas),
        aggregate_metrics=aggregate_metrics,
        generated_at=datetime.now(timezone.utc),
    )


def _compute_criterion_deltas(
    *,
    baseline_apps: list[RubricApplication],
    candidate_apps: list[RubricApplication],
    baseline_criteria_by_id: dict[UUID, Criterion],
    candidate_criteria_by_id: dict[UUID, Criterion],
    baseline_criteria_by_name: dict[str, Criterion],
    candidate_criteria_by_name: dict[str, Criterion],
) -> list[CriterionDelta]:
    baseline_by_name = _index_apps_by_criterion_name(
        baseline_apps, baseline_criteria_by_id
    )
    candidate_by_name = _index_apps_by_criterion_name(
        candidate_apps, candidate_criteria_by_id
    )
    all_names = sorted(set(baseline_by_name) | set(candidate_by_name))

    deltas: list[CriterionDelta] = []
    for name in all_names:
        baseline_for_name = baseline_by_name.get(name, [])
        candidate_for_name = candidate_by_name.get(name, [])
        baseline_criterion = baseline_criteria_by_name.get(name)
        candidate_criterion = candidate_criteria_by_name.get(name)
        baseline_success = (
            _count_successful_for_criterion(
                baseline_for_name, baseline_criterion
            )
            if baseline_criterion is not None
            else 0
        )
        candidate_success = (
            _count_successful_for_criterion(
                candidate_for_name, candidate_criterion
            )
            if candidate_criterion is not None
            else 0
        )
        baseline_count = len(baseline_for_name)
        candidate_count = len(candidate_for_name)
        baseline_rate = (
            baseline_success / baseline_count if baseline_count else 0.0
        )
        candidate_rate = (
            candidate_success / candidate_count if candidate_count else 0.0
        )
        deltas.append(
            CriterionDelta(
                criterion_name=name,
                baseline_success_rate=baseline_rate,
                candidate_success_rate=candidate_rate,
                delta=candidate_rate - baseline_rate,
                baseline_count=baseline_count,
                candidate_count=candidate_count,
            )
        )
    return deltas


def _index_apps_by_criterion_name(
    apps: list[RubricApplication],
    criteria_by_id: dict[UUID, Criterion],
) -> dict[str, list[RubricApplication]]:
    out: dict[str, list[RubricApplication]] = {}
    for app in apps:
        criterion = criteria_by_id.get(app.criterion_id)
        if criterion is None:
            # Defensive: a rubric_application referencing a criterion
            # not in the revision's set is data drift; skip it (the
            # foreign key on rubric_applications.criterion_id makes
            # this unreachable in practice).
            continue
        out.setdefault(criterion.name, []).append(app)
    return out


def _count_successful_for_criterion(
    apps: list[RubricApplication], criterion: Criterion
) -> int:
    count = 0
    for app in apps:
        if app.automated_score is None:
            continue
        for level in criterion.levels:
            if level.label == app.automated_score:
                if level.is_success:
                    count += 1
                break
    return count


def _count_successful(
    apps: list[RubricApplication],
    criteria_by_id: dict[UUID, Criterion],
) -> int:
    count = 0
    for app in apps:
        criterion = criteria_by_id.get(app.criterion_id)
        if criterion is None:
            continue
        if app.automated_score is None:
            continue
        for level in criterion.levels:
            if level.label == app.automated_score:
                if level.is_success:
                    count += 1
                break
    return count
