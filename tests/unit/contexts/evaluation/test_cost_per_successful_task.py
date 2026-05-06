"""Unit tests for the cost_per_successful_task use case.

Exercises the algorithm against in-memory fakes for the scoring-sheet
repository, rubric-application repository, and CostQueryPort. Covers
the four canonical paths the use case must handle:

  - all-successful: every rubric_application matches a successful
    level, every trace_id has cost data → clean numerator and
    denominator.
  - mixed success: some applications fail, only successful ones are
    counted in the numerator and divisor.
  - excluded-trace-id: successful applications without trace_id (or
    with trace_id but no cost data) inflate excluded_count and
    contribute zero to total_cost_usd, but still count toward the
    denominator.
  - empty-set: no rubric_applications → zero result; no port calls.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from contexts.evaluation.application.cost_per_successful_task import (
    cost_per_successful_task,
)
from contexts.evaluation.domain.applier import ApplierConfig, ApplierType
from contexts.evaluation.domain.rubric_application import RubricApplication
from contexts.evaluation.domain.scoring_sheet import Criterion, CriterionLevel
from contexts.observability.domain.cost import CostBreakdown
from shared_kernel import TenantContext


# ---------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------


class _FakeScoringSheetRepository:
    def __init__(
        self, pairs: list[tuple[Criterion, ApplierConfig]]
    ) -> None:
        self._pairs = pairs

    async def get_criteria_with_appliers(
        self, scoring_sheet_revision_id: UUID
    ) -> list[tuple[Criterion, ApplierConfig]]:
        return self._pairs


class _FakeRubricApplicationRepository:
    def __init__(self, apps: list[RubricApplication]) -> None:
        self._apps = apps

    async def save(self, rubric_application: RubricApplication) -> None:
        self._apps.append(rubric_application)

    async def list_for_revision_and_set(
        self,
        scoring_sheet_revision_id: UUID,
        interaction_set_id: UUID,
    ) -> list[RubricApplication]:
        return list(self._apps)


class _FakeCostQueryPort:
    def __init__(self, costs: dict[str, CostBreakdown]) -> None:
        self._costs = costs
        self.calls: list[tuple[tuple[str, ...], str]] = []

    async def get_costs_by_trace_ids(
        self,
        trace_ids: list[str],
        tenant_context: TenantContext,
    ) -> dict[str, CostBreakdown]:
        self.calls.append((tuple(trace_ids), tenant_context.tenant_id))
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


def _criterion(id_: UUID, revision_id: UUID, *, name: str = "c") -> Criterion:
    return Criterion(
        id=id_,
        scoring_sheet_revision_id=revision_id,
        name=name,
        description=f"{name} criterion",
        levels=(
            CriterionLevel(label="pass", definition="pass", is_success=True),
            CriterionLevel(label="fail", definition="fail", is_success=False),
        ),
        ordering=0,
    )


def _app(
    *,
    revision_id: UUID,
    criterion_id: UUID,
    score: str | None,
    trace_id: str | None,
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


def _applier_config(revision_id: UUID, criterion_id: UUID) -> ApplierConfig:
    return ApplierConfig(
        id=uuid4(),
        scoring_sheet_revision_id=revision_id,
        criterion_id=criterion_id,
        applier_type=ApplierType.DETERMINISTIC,
        deterministic_function_name="exact_match",
    )


# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------


def test_all_successful_path_returns_clean_aggregate() -> None:
    """Two interactions × two criteria, every application successful,
    every trace_id has cost data. Two unique trace_ids (one per
    interaction); cost summed across them; divisor is 4 (count of
    successful applications, not unique trace_ids)."""
    revision_id = uuid4()
    crit_a_id = uuid4()
    crit_b_id = uuid4()
    crit_a = _criterion(crit_a_id, revision_id, name="a")
    crit_b = _criterion(crit_b_id, revision_id, name="b")
    apps = [
        _app(
            revision_id=revision_id,
            criterion_id=crit_a_id,
            score="pass",
            trace_id="trace-1",
        ),
        _app(
            revision_id=revision_id,
            criterion_id=crit_b_id,
            score="pass",
            trace_id="trace-1",
        ),
        _app(
            revision_id=revision_id,
            criterion_id=crit_a_id,
            score="pass",
            trace_id="trace-2",
        ),
        _app(
            revision_id=revision_id,
            criterion_id=crit_b_id,
            score="pass",
            trace_id="trace-2",
        ),
    ]
    sheet = _FakeScoringSheetRepository(
        pairs=[
            (crit_a, _applier_config(revision_id, crit_a_id)),
            (crit_b, _applier_config(revision_id, crit_b_id)),
        ]
    )
    rubric = _FakeRubricApplicationRepository(apps=apps)
    costs = _FakeCostQueryPort(
        costs={
            "trace-1": CostBreakdown(
                total_usd=Decimal("0.10"),
                input_usd=Decimal("0.04"),
                output_usd=Decimal("0.06"),
            ),
            "trace-2": CostBreakdown(
                total_usd=Decimal("0.20"),
                input_usd=Decimal("0.08"),
                output_usd=Decimal("0.12"),
            ),
        }
    )

    result = asyncio.run(
        cost_per_successful_task(
            tenant_context=_ctx(),
            scoring_sheet_revision_id=revision_id,
            interaction_set_id=uuid4(),
            scoring_sheet_repository=sheet,
            rubric_application_repository=rubric,
            cost_query_port=costs,
        )
    )

    assert result.successful_count == 4
    assert result.total_cost_usd == Decimal("0.30")
    assert result.cost_per_task_usd == Decimal("0.30") / 4
    assert result.excluded_count == 0
    # Only unique trace_ids are queried (deduplication before cost
    # call).
    assert len(costs.calls) == 1
    queried, tid = costs.calls[0]
    assert sorted(queried) == ["trace-1", "trace-2"]
    assert tid == _ctx().tenant_id


def test_mixed_success_path_filters_by_is_success_label() -> None:
    """Two applications, one passes and one fails. Only the passing
    one counts toward successful_count; only its trace_id is queried.
    """
    revision_id = uuid4()
    crit_id = uuid4()
    crit = _criterion(crit_id, revision_id)
    apps = [
        _app(
            revision_id=revision_id,
            criterion_id=crit_id,
            score="pass",
            trace_id="trace-1",
        ),
        _app(
            revision_id=revision_id,
            criterion_id=crit_id,
            score="fail",
            trace_id="trace-2",
        ),
    ]
    sheet = _FakeScoringSheetRepository(
        pairs=[(crit, _applier_config(revision_id, crit_id))]
    )
    rubric = _FakeRubricApplicationRepository(apps=apps)
    costs = _FakeCostQueryPort(
        costs={
            "trace-1": CostBreakdown(
                total_usd=Decimal("0.10"),
                input_usd=Decimal("0.04"),
                output_usd=Decimal("0.06"),
            )
        }
    )

    result = asyncio.run(
        cost_per_successful_task(
            tenant_context=_ctx(),
            scoring_sheet_revision_id=revision_id,
            interaction_set_id=uuid4(),
            scoring_sheet_repository=sheet,
            rubric_application_repository=rubric,
            cost_query_port=costs,
        )
    )

    assert result.successful_count == 1
    assert result.total_cost_usd == Decimal("0.10")
    assert result.cost_per_task_usd == Decimal("0.10")
    assert result.excluded_count == 0
    queried, _ = costs.calls[0]
    assert sorted(queried) == ["trace-1"]


def test_excluded_path_counts_apps_without_trace_id_or_cost() -> None:
    """Three successful applications: one with cost, one without
    trace_id, one with trace_id but no cost data. excluded_count==2;
    divisor is 3.
    """
    revision_id = uuid4()
    crit_id = uuid4()
    crit = _criterion(crit_id, revision_id)
    apps = [
        _app(
            revision_id=revision_id,
            criterion_id=crit_id,
            score="pass",
            trace_id="trace-with-cost",
        ),
        _app(
            revision_id=revision_id,
            criterion_id=crit_id,
            score="pass",
            trace_id=None,
        ),
        _app(
            revision_id=revision_id,
            criterion_id=crit_id,
            score="pass",
            trace_id="trace-no-cost",
        ),
    ]
    sheet = _FakeScoringSheetRepository(
        pairs=[(crit, _applier_config(revision_id, crit_id))]
    )
    rubric = _FakeRubricApplicationRepository(apps=apps)
    costs = _FakeCostQueryPort(
        costs={
            "trace-with-cost": CostBreakdown(
                total_usd=Decimal("0.30"),
                input_usd=Decimal("0.10"),
                output_usd=Decimal("0.20"),
            )
            # "trace-no-cost" deliberately absent
        }
    )

    result = asyncio.run(
        cost_per_successful_task(
            tenant_context=_ctx(),
            scoring_sheet_revision_id=revision_id,
            interaction_set_id=uuid4(),
            scoring_sheet_repository=sheet,
            rubric_application_repository=rubric,
            cost_query_port=costs,
        )
    )

    assert result.successful_count == 3
    assert result.total_cost_usd == Decimal("0.30")
    assert result.cost_per_task_usd == Decimal("0.30") / 3
    assert result.excluded_count == 2  # trace-id-None + trace-no-cost


def test_empty_rubric_applications_returns_zero_result_without_querying_cost() -> None:
    revision_id = uuid4()
    sheet = _FakeScoringSheetRepository(pairs=[])
    rubric = _FakeRubricApplicationRepository(apps=[])
    costs = _FakeCostQueryPort(costs={})

    result = asyncio.run(
        cost_per_successful_task(
            tenant_context=_ctx(),
            scoring_sheet_revision_id=revision_id,
            interaction_set_id=uuid4(),
            scoring_sheet_repository=sheet,
            rubric_application_repository=rubric,
            cost_query_port=costs,
        )
    )

    assert result == _zero_result()
    assert costs.calls == []  # no point querying with no successful set


def _zero_result():
    from contexts.evaluation.domain.cost_per_successful_task_result import (
        CostPerSuccessfulTaskResult,
    )

    return CostPerSuccessfulTaskResult(
        total_cost_usd=Decimal("0"),
        successful_count=0,
        cost_per_task_usd=Decimal("0"),
        excluded_count=0,
    )
