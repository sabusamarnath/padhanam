"""Unit tests for the render_text and render_json functions (D58, S18).

The render functions are pure over a ``RegressionReport`` instance.
Tests construct a small report directly (not via compare_runs) and
assert structural properties of the rendered output:

  - render_text produces a markdown document with a per-criterion
    table and an aggregate section.
  - render_json produces parseable JSON whose shape matches the
    domain entities.
  - Decimal cost values render as strings in JSON so monetary
    precision is preserved.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from contexts.evaluation.application.render_report import (
    render_json,
    render_text,
)
from contexts.evaluation.domain.regression_report import (
    AggregateMetrics,
    CriterionDelta,
    RegressionReport,
)


def _sample_report() -> RegressionReport:
    return RegressionReport(
        baseline_revision_id=uuid4(),
        candidate_revision_id=uuid4(),
        interaction_set_id=uuid4(),
        per_criterion_deltas=(
            CriterionDelta(
                criterion_name="accuracy",
                baseline_success_rate=0.5,
                candidate_success_rate=0.75,
                delta=0.25,
                baseline_count=4,
                candidate_count=4,
            ),
            CriterionDelta(
                criterion_name="format",
                baseline_success_rate=1.0,
                candidate_success_rate=0.5,
                delta=-0.5,
                baseline_count=2,
                candidate_count=2,
            ),
        ),
        aggregate_metrics=AggregateMetrics(
            total_baseline_applications=6,
            total_candidate_applications=6,
            total_baseline_successful=4,
            total_candidate_successful=4,
            overall_baseline_success_rate=4 / 6,
            overall_candidate_success_rate=4 / 6,
            overall_success_rate_delta=0.0,
            baseline_cost_per_task_usd=Decimal("0.001234"),
            candidate_cost_per_task_usd=Decimal("0.000900"),
            overall_cost_per_task_delta_usd=Decimal("-0.000334"),
        ),
        generated_at=datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc),
    )


def test_render_text_contains_header_table_and_aggregate() -> None:
    out = render_text(_sample_report())
    assert "# Regression report" in out
    assert "Baseline revision:" in out
    assert "Candidate revision:" in out
    # Per-criterion table renders both criteria with pct values
    assert "accuracy" in out
    assert "50.0%" in out
    assert "75.0%" in out
    assert "+25.0%" in out
    assert "format" in out
    assert "-50.0%" in out
    # Aggregate section renders cost values and the delta
    assert "Baseline cost per task" in out
    assert "$0.001234 USD" in out
    assert "$0.000900 USD" in out
    assert "-$0.000334 USD" in out


def test_render_text_handles_empty_per_criterion_set() -> None:
    report = RegressionReport(
        baseline_revision_id=uuid4(),
        candidate_revision_id=uuid4(),
        interaction_set_id=uuid4(),
        per_criterion_deltas=(),
        aggregate_metrics=AggregateMetrics(
            total_baseline_applications=0,
            total_candidate_applications=0,
            total_baseline_successful=0,
            total_candidate_successful=0,
            overall_baseline_success_rate=0.0,
            overall_candidate_success_rate=0.0,
            overall_success_rate_delta=0.0,
            baseline_cost_per_task_usd=Decimal("0"),
            candidate_cost_per_task_usd=Decimal("0"),
            overall_cost_per_task_delta_usd=Decimal("0"),
        ),
        generated_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
    )
    out = render_text(report)
    assert "(no criteria with rubric_applications on either side)" in out


def test_render_json_round_trips_to_dict_with_string_decimals() -> None:
    report = _sample_report()
    out = render_json(report)
    data = json.loads(out)

    assert data["baseline_revision_id"] == str(report.baseline_revision_id)
    assert data["candidate_revision_id"] == str(report.candidate_revision_id)
    assert data["interaction_set_id"] == str(report.interaction_set_id)
    assert data["generated_at"] == report.generated_at.isoformat()

    assert len(data["per_criterion_deltas"]) == 2
    accuracy = data["per_criterion_deltas"][0]
    assert accuracy["criterion_name"] == "accuracy"
    assert accuracy["baseline_success_rate"] == 0.5
    assert accuracy["candidate_success_rate"] == 0.75
    assert accuracy["delta"] == 0.25
    assert accuracy["baseline_count"] == 4
    assert accuracy["candidate_count"] == 4

    metrics = data["aggregate_metrics"]
    # Decimals as strings — preserves monetary precision through
    # JSON serialisation.
    assert metrics["baseline_cost_per_task_usd"] == "0.001234"
    assert metrics["candidate_cost_per_task_usd"] == "0.000900"
    assert metrics["overall_cost_per_task_delta_usd"] == "-0.000334"
