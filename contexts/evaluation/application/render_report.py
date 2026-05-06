"""Render functions for ``RegressionReport`` (D58, S18).

Two output formats:

  - ``render_text`` — human-readable markdown table, the operator's
    surface at the CLI runner. Carries per-criterion rows and an
    aggregate footer; readable in a terminal without further tooling.

  - ``render_json`` — structured JSON for programmatic consumers
    (the P11 recommendation engine reads regression reports as
    evidence input). Decimal cost values render as strings (JSON
    has no Decimal type; string preserves precision); UUIDs render
    as strings; datetime renders as ISO-8601.

Both formats are pure functions over a ``RegressionReport`` instance;
no I/O, no dependencies, no side effects. The CLI commits to writing
the output to stdout or a file at the caller layer.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from contexts.evaluation.domain.regression_report import (
    AggregateMetrics,
    CriterionDelta,
    RegressionReport,
)


def render_text(report: RegressionReport) -> str:
    """Render the report as a human-readable markdown document.

    The table is markdown-shaped so it can be pasted into a
    GitHub PR description, a Slack message, or a session log
    entry without further formatting. Numeric columns render as
    percentages (success rate) or USD-prefixed Decimal strings
    (cost) because both consumers — the operator at the terminal
    and the operator pasting into a procurement-shaped PR — read
    those forms directly.
    """
    lines: list[str] = []
    lines.append("# Regression report")
    lines.append("")
    lines.append(f"Baseline revision: `{report.baseline_revision_id}`")
    lines.append(f"Candidate revision: `{report.candidate_revision_id}`")
    lines.append(f"Interaction set: `{report.interaction_set_id}`")
    lines.append(f"Generated at: {report.generated_at.isoformat()}")
    lines.append("")
    lines.append("## Per-criterion deltas")
    lines.append("")
    if report.per_criterion_deltas:
        lines.append(
            "| Criterion | Baseline | Candidate | Δ | Baseline N | Candidate N |"
        )
        lines.append(
            "| --- | ---: | ---: | ---: | ---: | ---: |"
        )
        for delta in report.per_criterion_deltas:
            lines.append(_render_criterion_delta_row(delta))
    else:
        lines.append("(no criteria with rubric_applications on either side)")
    lines.append("")
    lines.append("## Aggregate metrics")
    lines.append("")
    lines.extend(_render_aggregate_metrics_lines(report.aggregate_metrics))
    return "\n".join(lines) + "\n"


def render_json(report: RegressionReport) -> str:
    """Render the report as structured JSON.

    Decimal values render as strings to preserve monetary precision
    (``json`` has no Decimal type; the float fallback would surrender
    precision the cost path goes out of its way to keep). UUIDs and
    datetimes render as strings. The shape is regular enough that a
    typed decoder can rehydrate it without ambiguity.
    """
    return json.dumps(_report_to_dict(report), indent=2, sort_keys=False)


def _render_criterion_delta_row(delta: CriterionDelta) -> str:
    return (
        f"| {delta.criterion_name} "
        f"| {_format_rate(delta.baseline_success_rate)} "
        f"| {_format_rate(delta.candidate_success_rate)} "
        f"| {_format_rate_delta(delta.delta)} "
        f"| {delta.baseline_count} "
        f"| {delta.candidate_count} |"
    )


def _render_aggregate_metrics_lines(metrics: AggregateMetrics) -> list[str]:
    return [
        f"- Total baseline applications: {metrics.total_baseline_applications}",
        f"- Total candidate applications: {metrics.total_candidate_applications}",
        f"- Total baseline successful: {metrics.total_baseline_successful}",
        f"- Total candidate successful: {metrics.total_candidate_successful}",
        f"- Baseline success rate: {_format_rate(metrics.overall_baseline_success_rate)}",
        f"- Candidate success rate: {_format_rate(metrics.overall_candidate_success_rate)}",
        f"- Overall success rate Δ: {_format_rate_delta(metrics.overall_success_rate_delta)}",
        f"- Baseline cost per task: {_format_cost(metrics.baseline_cost_per_task_usd)}",
        f"- Candidate cost per task: {_format_cost(metrics.candidate_cost_per_task_usd)}",
        f"- Overall cost per task Δ: {_format_cost_delta(metrics.overall_cost_per_task_delta_usd)}",
    ]


def _format_rate(rate: float) -> str:
    return f"{rate * 100:.1f}%"


def _format_rate_delta(delta: float) -> str:
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta * 100:.1f}%"


def _format_cost(cost: Decimal) -> str:
    return f"${cost:.6f} USD"


def _format_cost_delta(delta: Decimal) -> str:
    if delta >= 0:
        return f"+${delta:.6f} USD"
    return f"-${abs(delta):.6f} USD"


def _report_to_dict(report: RegressionReport) -> dict:
    return {
        "baseline_revision_id": str(report.baseline_revision_id),
        "candidate_revision_id": str(report.candidate_revision_id),
        "interaction_set_id": str(report.interaction_set_id),
        "generated_at": _datetime_to_iso(report.generated_at),
        "per_criterion_deltas": [
            _criterion_delta_to_dict(d) for d in report.per_criterion_deltas
        ],
        "aggregate_metrics": _aggregate_metrics_to_dict(
            report.aggregate_metrics
        ),
    }


def _criterion_delta_to_dict(delta: CriterionDelta) -> dict:
    return {
        "criterion_name": delta.criterion_name,
        "baseline_success_rate": delta.baseline_success_rate,
        "candidate_success_rate": delta.candidate_success_rate,
        "delta": delta.delta,
        "baseline_count": delta.baseline_count,
        "candidate_count": delta.candidate_count,
    }


def _aggregate_metrics_to_dict(metrics: AggregateMetrics) -> dict:
    return {
        "total_baseline_applications": metrics.total_baseline_applications,
        "total_candidate_applications": metrics.total_candidate_applications,
        "total_baseline_successful": metrics.total_baseline_successful,
        "total_candidate_successful": metrics.total_candidate_successful,
        "overall_baseline_success_rate": metrics.overall_baseline_success_rate,
        "overall_candidate_success_rate": metrics.overall_candidate_success_rate,
        "overall_success_rate_delta": metrics.overall_success_rate_delta,
        "baseline_cost_per_task_usd": str(metrics.baseline_cost_per_task_usd),
        "candidate_cost_per_task_usd": str(metrics.candidate_cost_per_task_usd),
        "overall_cost_per_task_delta_usd": str(
            metrics.overall_cost_per_task_delta_usd
        ),
    }


def _datetime_to_iso(value: datetime) -> str:
    return value.isoformat()
