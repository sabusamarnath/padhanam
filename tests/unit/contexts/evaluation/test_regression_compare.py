"""Unit tests for the compare_runs use case (D58, S18).

Exercises the comparison algorithm against in-memory fakes for the
scoring-sheet repository, rubric-application repository, and
CostQueryPort. Covers:

  - identical-runs (zero deltas across criteria and aggregate)
  - all-improvements (every criterion candidate > baseline)
  - all-regressions (every criterion candidate < baseline)
  - mixed (some up, some down)
  - single-criterion
  - multi-criterion
  - asymmetric criteria (criterion only on baseline, only on
    candidate; the join-by-name shape handles the absence)

The fakes dispatch on revision_id because compare_runs calls each
read port twice — once for baseline, once for candidate — and
cost_per_successful_task internally repeats those reads on each side.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from contexts.evaluation.application.regression_compare import compare_runs
from contexts.evaluation.domain.applier import ApplierConfig, ApplierType
from contexts.evaluation.domain.rubric_application import RubricApplication
from contexts.evaluation.domain.scoring_sheet import Criterion, CriterionLevel
from contexts.observability.domain.cost import CostBreakdown
from shared_kernel import TenantContext


# ---------------------------------------------------------------------
# Fakes (dispatch on revision_id)
# ---------------------------------------------------------------------


class _FakeScoringSheetRepository:
    def __init__(
        self,
        pairs_by_revision: dict[UUID, list[tuple[Criterion, ApplierConfig]]],
    ) -> None:
        self._pairs_by_revision = pairs_by_revision

    async def get_criteria_with_appliers(
        self, scoring_sheet_revision_id: UUID
    ) -> list[tuple[Criterion, ApplierConfig]]:
        return list(self._pairs_by_revision.get(scoring_sheet_revision_id, []))


class _FakeRubricApplicationRepository:
    def __init__(
        self, apps_by_revision: dict[UUID, list[RubricApplication]]
    ) -> None:
        self._apps_by_revision = apps_by_revision

    async def save(self, rubric_application: RubricApplication) -> None:
        self._apps_by_revision.setdefault(
            rubric_application.scoring_sheet_revision_id, []
        ).append(rubric_application)

    async def list_for_revision_and_set(
        self,
        scoring_sheet_revision_id: UUID,
        interaction_set_id: UUID,
    ) -> list[RubricApplication]:
        return list(self._apps_by_revision.get(scoring_sheet_revision_id, []))


class _FakeCostQueryPort:
    def __init__(self, costs: dict[str, CostBreakdown]) -> None:
        self._costs = costs

    async def get_costs_by_trace_ids(
        self,
        trace_ids: list[str],
        tenant_context: TenantContext,
    ) -> dict[str, CostBreakdown]:
        return {tid: self._costs[tid] for tid in trace_ids if tid in self._costs}


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a001",
    )


def _criterion(*, name: str, revision_id: UUID) -> Criterion:
    return Criterion(
        id=uuid4(),
        scoring_sheet_revision_id=revision_id,
        name=name,
        description=f"{name} criterion",
        levels=(
            CriterionLevel(label="pass", definition="pass", is_success=True),
            CriterionLevel(label="fail", definition="fail", is_success=False),
        ),
        ordering=0,
    )


def _applier_for(criterion: Criterion) -> ApplierConfig:
    return ApplierConfig(
        id=uuid4(),
        scoring_sheet_revision_id=criterion.scoring_sheet_revision_id,
        criterion_id=criterion.id,
        applier_type=ApplierType.DETERMINISTIC,
        deterministic_function_name="exact_match",
    )


def _app(
    *,
    revision_id: UUID,
    criterion_id: UUID,
    score: str,
    trace_id: str | None = "trace-1",
) -> RubricApplication:
    return RubricApplication(
        id=uuid4(),
        scoring_sheet_revision_id=revision_id,
        criterion_id=criterion_id,
        interaction_id=uuid4(),
        applier_id=uuid4(),
        automated_score=score,
        human_score=None,
        reviewed_by_user_id=None,
        confirmed_at=None,
        created_at=datetime.now(timezone.utc),
        trace_id=trace_id,
    )


# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------


def test_identical_runs_produce_zero_deltas() -> None:
    """Two revisions with the same criterion name, the same per-app
    success outcomes — every delta should be zero."""
    baseline_id = uuid4()
    candidate_id = uuid4()
    interaction_set_id = uuid4()

    crit_b = _criterion(name="quality", revision_id=baseline_id)
    crit_c = _criterion(name="quality", revision_id=candidate_id)

    sheet = _FakeScoringSheetRepository(
        pairs_by_revision={
            baseline_id: [(crit_b, _applier_for(crit_b))],
            candidate_id: [(crit_c, _applier_for(crit_c))],
        }
    )
    rubric = _FakeRubricApplicationRepository(
        apps_by_revision={
            baseline_id: [
                _app(revision_id=baseline_id, criterion_id=crit_b.id, score="pass"),
                _app(revision_id=baseline_id, criterion_id=crit_b.id, score="fail"),
            ],
            candidate_id: [
                _app(revision_id=candidate_id, criterion_id=crit_c.id, score="pass"),
                _app(revision_id=candidate_id, criterion_id=crit_c.id, score="fail"),
            ],
        }
    )
    costs = _FakeCostQueryPort(costs={})

    report = asyncio.run(
        compare_runs(
            tenant_context=_ctx(),
            baseline_revision_id=baseline_id,
            candidate_revision_id=candidate_id,
            interaction_set_id=interaction_set_id,
            scoring_sheet_repository=sheet,
            rubric_application_repository=rubric,
            cost_query_port=costs,
        )
    )

    assert report.baseline_revision_id == baseline_id
    assert report.candidate_revision_id == candidate_id
    assert report.interaction_set_id == interaction_set_id
    assert len(report.per_criterion_deltas) == 1
    delta = report.per_criterion_deltas[0]
    assert delta.criterion_name == "quality"
    assert delta.baseline_success_rate == 0.5
    assert delta.candidate_success_rate == 0.5
    assert delta.delta == 0.0
    assert delta.baseline_count == 2
    assert delta.candidate_count == 2

    assert report.aggregate_metrics.total_baseline_applications == 2
    assert report.aggregate_metrics.total_candidate_applications == 2
    assert report.aggregate_metrics.total_baseline_successful == 1
    assert report.aggregate_metrics.total_candidate_successful == 1
    assert report.aggregate_metrics.overall_baseline_success_rate == 0.5
    assert report.aggregate_metrics.overall_candidate_success_rate == 0.5
    assert report.aggregate_metrics.overall_success_rate_delta == 0.0


def test_all_improvements_returns_positive_deltas() -> None:
    """Candidate scores higher than baseline on every criterion."""
    baseline_id = uuid4()
    candidate_id = uuid4()
    set_id = uuid4()

    crit_b = _criterion(name="accuracy", revision_id=baseline_id)
    crit_c = _criterion(name="accuracy", revision_id=candidate_id)

    sheet = _FakeScoringSheetRepository(
        pairs_by_revision={
            baseline_id: [(crit_b, _applier_for(crit_b))],
            candidate_id: [(crit_c, _applier_for(crit_c))],
        }
    )
    rubric = _FakeRubricApplicationRepository(
        apps_by_revision={
            # baseline: 1/4 pass = 25%
            baseline_id: [
                _app(revision_id=baseline_id, criterion_id=crit_b.id, score="pass"),
                _app(revision_id=baseline_id, criterion_id=crit_b.id, score="fail"),
                _app(revision_id=baseline_id, criterion_id=crit_b.id, score="fail"),
                _app(revision_id=baseline_id, criterion_id=crit_b.id, score="fail"),
            ],
            # candidate: 3/4 pass = 75%
            candidate_id: [
                _app(revision_id=candidate_id, criterion_id=crit_c.id, score="pass"),
                _app(revision_id=candidate_id, criterion_id=crit_c.id, score="pass"),
                _app(revision_id=candidate_id, criterion_id=crit_c.id, score="pass"),
                _app(revision_id=candidate_id, criterion_id=crit_c.id, score="fail"),
            ],
        }
    )
    costs = _FakeCostQueryPort(costs={})

    report = asyncio.run(
        compare_runs(
            tenant_context=_ctx(),
            baseline_revision_id=baseline_id,
            candidate_revision_id=candidate_id,
            interaction_set_id=set_id,
            scoring_sheet_repository=sheet,
            rubric_application_repository=rubric,
            cost_query_port=costs,
        )
    )

    delta = report.per_criterion_deltas[0]
    assert delta.baseline_success_rate == 0.25
    assert delta.candidate_success_rate == 0.75
    assert abs(delta.delta - 0.5) < 1e-9
    assert report.aggregate_metrics.overall_success_rate_delta > 0


def test_all_regressions_returns_negative_deltas() -> None:
    baseline_id = uuid4()
    candidate_id = uuid4()
    set_id = uuid4()

    crit_b = _criterion(name="accuracy", revision_id=baseline_id)
    crit_c = _criterion(name="accuracy", revision_id=candidate_id)

    sheet = _FakeScoringSheetRepository(
        pairs_by_revision={
            baseline_id: [(crit_b, _applier_for(crit_b))],
            candidate_id: [(crit_c, _applier_for(crit_c))],
        }
    )
    rubric = _FakeRubricApplicationRepository(
        apps_by_revision={
            baseline_id: [
                _app(revision_id=baseline_id, criterion_id=crit_b.id, score="pass"),
                _app(revision_id=baseline_id, criterion_id=crit_b.id, score="pass"),
            ],
            candidate_id: [
                _app(revision_id=candidate_id, criterion_id=crit_c.id, score="fail"),
                _app(revision_id=candidate_id, criterion_id=crit_c.id, score="fail"),
            ],
        }
    )
    costs = _FakeCostQueryPort(costs={})

    report = asyncio.run(
        compare_runs(
            tenant_context=_ctx(),
            baseline_revision_id=baseline_id,
            candidate_revision_id=candidate_id,
            interaction_set_id=set_id,
            scoring_sheet_repository=sheet,
            rubric_application_repository=rubric,
            cost_query_port=costs,
        )
    )

    delta = report.per_criterion_deltas[0]
    assert delta.baseline_success_rate == 1.0
    assert delta.candidate_success_rate == 0.0
    assert delta.delta == -1.0
    assert report.aggregate_metrics.overall_success_rate_delta == -1.0


def test_multi_criterion_mixed_deltas() -> None:
    """Two criteria, one improves and one regresses."""
    baseline_id = uuid4()
    candidate_id = uuid4()
    set_id = uuid4()

    crit_b_acc = _criterion(name="accuracy", revision_id=baseline_id)
    crit_b_form = _criterion(name="format", revision_id=baseline_id)
    crit_c_acc = _criterion(name="accuracy", revision_id=candidate_id)
    crit_c_form = _criterion(name="format", revision_id=candidate_id)

    sheet = _FakeScoringSheetRepository(
        pairs_by_revision={
            baseline_id: [
                (crit_b_acc, _applier_for(crit_b_acc)),
                (crit_b_form, _applier_for(crit_b_form)),
            ],
            candidate_id: [
                (crit_c_acc, _applier_for(crit_c_acc)),
                (crit_c_form, _applier_for(crit_c_form)),
            ],
        }
    )
    rubric = _FakeRubricApplicationRepository(
        apps_by_revision={
            # accuracy: baseline 1/2, candidate 2/2 → +50%
            # format:   baseline 2/2, candidate 1/2 → -50%
            baseline_id: [
                _app(revision_id=baseline_id, criterion_id=crit_b_acc.id, score="pass"),
                _app(revision_id=baseline_id, criterion_id=crit_b_acc.id, score="fail"),
                _app(revision_id=baseline_id, criterion_id=crit_b_form.id, score="pass"),
                _app(revision_id=baseline_id, criterion_id=crit_b_form.id, score="pass"),
            ],
            candidate_id: [
                _app(revision_id=candidate_id, criterion_id=crit_c_acc.id, score="pass"),
                _app(revision_id=candidate_id, criterion_id=crit_c_acc.id, score="pass"),
                _app(revision_id=candidate_id, criterion_id=crit_c_form.id, score="pass"),
                _app(revision_id=candidate_id, criterion_id=crit_c_form.id, score="fail"),
            ],
        }
    )
    costs = _FakeCostQueryPort(costs={})

    report = asyncio.run(
        compare_runs(
            tenant_context=_ctx(),
            baseline_revision_id=baseline_id,
            candidate_revision_id=candidate_id,
            interaction_set_id=set_id,
            scoring_sheet_repository=sheet,
            rubric_application_repository=rubric,
            cost_query_port=costs,
        )
    )

    by_name = {d.criterion_name: d for d in report.per_criterion_deltas}
    assert sorted(by_name) == ["accuracy", "format"]
    assert abs(by_name["accuracy"].delta - 0.5) < 1e-9
    assert abs(by_name["format"].delta + 0.5) < 1e-9
    # Aggregate net: 3/4 vs 3/4 = 0
    assert report.aggregate_metrics.overall_success_rate_delta == 0.0


def test_asymmetric_criteria_handles_missing_side() -> None:
    """A criterion that exists only in baseline (or only in candidate)
    appears in the report with zero on the missing side and the
    structural counts to interpret it."""
    baseline_id = uuid4()
    candidate_id = uuid4()
    set_id = uuid4()

    crit_b_only = _criterion(name="legacy_check", revision_id=baseline_id)
    crit_c_only = _criterion(name="new_check", revision_id=candidate_id)

    sheet = _FakeScoringSheetRepository(
        pairs_by_revision={
            baseline_id: [(crit_b_only, _applier_for(crit_b_only))],
            candidate_id: [(crit_c_only, _applier_for(crit_c_only))],
        }
    )
    rubric = _FakeRubricApplicationRepository(
        apps_by_revision={
            baseline_id: [
                _app(
                    revision_id=baseline_id,
                    criterion_id=crit_b_only.id,
                    score="pass",
                ),
            ],
            candidate_id: [
                _app(
                    revision_id=candidate_id,
                    criterion_id=crit_c_only.id,
                    score="fail",
                ),
            ],
        }
    )
    costs = _FakeCostQueryPort(costs={})

    report = asyncio.run(
        compare_runs(
            tenant_context=_ctx(),
            baseline_revision_id=baseline_id,
            candidate_revision_id=candidate_id,
            interaction_set_id=set_id,
            scoring_sheet_repository=sheet,
            rubric_application_repository=rubric,
            cost_query_port=costs,
        )
    )

    by_name = {d.criterion_name: d for d in report.per_criterion_deltas}
    assert by_name["legacy_check"].baseline_count == 1
    assert by_name["legacy_check"].candidate_count == 0
    assert by_name["legacy_check"].baseline_success_rate == 1.0
    assert by_name["legacy_check"].candidate_success_rate == 0.0
    assert by_name["new_check"].baseline_count == 0
    assert by_name["new_check"].candidate_count == 1
    assert by_name["new_check"].baseline_success_rate == 0.0
    assert by_name["new_check"].candidate_success_rate == 0.0


def test_cost_delta_propagated_from_cost_per_successful_task() -> None:
    """Aggregate cost-per-task deltas reflect the configured
    CostQueryPort — candidate cheaper than baseline returns a
    negative cost delta."""
    baseline_id = uuid4()
    candidate_id = uuid4()
    set_id = uuid4()

    crit_b = _criterion(name="quality", revision_id=baseline_id)
    crit_c = _criterion(name="quality", revision_id=candidate_id)

    sheet = _FakeScoringSheetRepository(
        pairs_by_revision={
            baseline_id: [(crit_b, _applier_for(crit_b))],
            candidate_id: [(crit_c, _applier_for(crit_c))],
        }
    )
    rubric = _FakeRubricApplicationRepository(
        apps_by_revision={
            baseline_id: [
                _app(
                    revision_id=baseline_id,
                    criterion_id=crit_b.id,
                    score="pass",
                    trace_id="b-trace",
                ),
            ],
            candidate_id: [
                _app(
                    revision_id=candidate_id,
                    criterion_id=crit_c.id,
                    score="pass",
                    trace_id="c-trace",
                ),
            ],
        }
    )
    costs = _FakeCostQueryPort(
        costs={
            "b-trace": CostBreakdown(
                total_usd=Decimal("0.20"),
                input_usd=Decimal("0.08"),
                output_usd=Decimal("0.12"),
            ),
            "c-trace": CostBreakdown(
                total_usd=Decimal("0.05"),
                input_usd=Decimal("0.02"),
                output_usd=Decimal("0.03"),
            ),
        }
    )

    report = asyncio.run(
        compare_runs(
            tenant_context=_ctx(),
            baseline_revision_id=baseline_id,
            candidate_revision_id=candidate_id,
            interaction_set_id=set_id,
            scoring_sheet_repository=sheet,
            rubric_application_repository=rubric,
            cost_query_port=costs,
        )
    )

    metrics = report.aggregate_metrics
    assert metrics.baseline_cost_per_task_usd == Decimal("0.20")
    assert metrics.candidate_cost_per_task_usd == Decimal("0.05")
    assert metrics.overall_cost_per_task_delta_usd == Decimal("-0.15")
