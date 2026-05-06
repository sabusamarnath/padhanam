"""Async eval orchestration for the CLI (S18).

Two top-level coroutines, ``run_eval`` and ``run_report``, called by
the typer commands at ``apps/cli/main.py``. Each coroutine owns the
composition lifecycle: build the wiring bundle, invoke the
application-layer use cases, dispose engines and HTTP clients
deterministically.

Composition is dev-shaped (TenantPostgresSettings.for_tenant,
hardcoded test-set tenant UUIDs) per ``apps/cli/_runtime.py``.
Phase 2 production CLI replaces the wiring with registry-driven
resolution mirroring apps/api/main.py; the orchestration shape
here is unchanged.

run_eval flow:
  1. Resolve tenant + session factory.
  2. Init OTel TracerProvider for trace_id propagation.
  3. Construct adapters (LiteLLM inference, Polymorphic applier,
     CostQueryAdapter wrapping LangfuseHTTPTraceQueryAdapter,
     three Postgres repositories).
  4. Run replay_and_score for the candidate revision (and baseline,
     if --baseline-revision-id given).
  5. Force-flush OTel to push spans to Langfuse OTLP receiver.
  6. Wait for each produced trace to be queryable per D59
     (replaces S17b's force-flush-and-sleep with polling-with-
     timeout).
  7. Either run cost_per_successful_task (single-revision) or
     compare_runs (regression).
  8. Render the result via render_text or render_json and return
     the rendered string for the CLI to emit.

run_report flow: skip replay; load from stored rubric_applications;
compare; render. Cost queries still run but no polling since the
replay is presumed historical.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from contexts.evaluation.adapters.outbound.cost_query_adapter import (
    CostQueryAdapter,
)
from contexts.evaluation.adapters.outbound.inference_adapter import (
    InferenceAdapter,
)
from contexts.evaluation.adapters.outbound.polymorphic_applier import (
    PolymorphicApplier,
)
from contexts.evaluation.adapters.outbound.postgres.interaction_repository import (
    PostgresInteractionRepository,
)
from contexts.evaluation.adapters.outbound.postgres.rubric_application_repository import (
    PostgresRubricApplicationRepository,
)
from contexts.evaluation.adapters.outbound.postgres.scoring_sheet_repository import (
    PostgresScoringSheetRepository,
)
from contexts.evaluation.application.apply_scoring_sheet import (
    apply_scoring_sheet,
)
from contexts.evaluation.application.cost_per_successful_task import (
    cost_per_successful_task,
)
from contexts.evaluation.application.regression_compare import compare_runs
from contexts.evaluation.application.render_report import (
    render_json,
    render_text,
)
from contexts.evaluation.application.replay_and_score import replay_and_score
from contexts.evaluation.domain.cost_per_successful_task_result import (
    CostPerSuccessfulTaskResult,
)
from contexts.evaluation.domain.model_config import ModelConfig
from contexts.evaluation.domain.regression_report import RegressionReport
from contexts.evaluation.domain.rubric_application import RubricApplication
from contexts.inference.adapters.outbound.litellm import LiteLLMAdapter
from contexts.observability.adapters.outbound.langfuse.http_adapter import (
    LangfuseHTTPTraceQueryAdapter,
)
from padhanam.config import InferenceSettings

from apps.cli._runtime import build_tenant_wiring, init_tracing


_OUTPUT_FORMAT_JSON = "json"


async def run_eval(
    *,
    tenant_id: str,
    interaction_set_id: UUID,
    candidate_revision_id: UUID,
    model_name: str,
    baseline_revision_id: Optional[UUID],
    output_format: str,
    poll_timeout_seconds: float,
) -> str:
    wiring = build_tenant_wiring(tenant_id)
    provider = init_tracing()
    trace_query_port = LangfuseHTTPTraceQueryAdapter()

    sheet_repo = PostgresScoringSheetRepository(wiring.session_factory)
    rubric_repo = PostgresRubricApplicationRepository(wiring.session_factory)
    interaction_repo = PostgresInteractionRepository(wiring.session_factory)
    cost_query_adapter = CostQueryAdapter(trace_query_port=trace_query_port)
    litellm_port = LiteLLMAdapter(settings=InferenceSettings())
    inference_adapter = InferenceAdapter(inference_port=litellm_port)
    applier = PolymorphicApplier(
        inference_port=inference_adapter,
        tenant_context=wiring.tenant_context,
    )

    try:
        candidate_apps = await replay_and_score(
            tenant_context=wiring.tenant_context,
            scoring_sheet_revision_id=candidate_revision_id,
            interaction_set_id=interaction_set_id,
            model_config=ModelConfig(model_name=model_name),
            inference_port=inference_adapter,
            interaction_repository=interaction_repo,
            scoring_sheet_repository=sheet_repo,
            rubric_application_repository=rubric_repo,
            applier=applier,
            apply_scoring_sheet=apply_scoring_sheet,
        )

        baseline_apps: list[RubricApplication] = []
        if baseline_revision_id is not None:
            baseline_apps = await replay_and_score(
                tenant_context=wiring.tenant_context,
                scoring_sheet_revision_id=baseline_revision_id,
                interaction_set_id=interaction_set_id,
                model_config=ModelConfig(model_name=model_name),
                inference_port=inference_adapter,
                interaction_repository=interaction_repo,
                scoring_sheet_repository=sheet_repo,
                rubric_application_repository=rubric_repo,
                applier=applier,
                apply_scoring_sheet=apply_scoring_sheet,
            )

        # D59: poll Langfuse for trace availability before cost
        # queries. Replaces S17b's 8s force-flush-and-sleep. The
        # provider.force_flush ensures the BatchSpanProcessor exits
        # spans synchronously to OTLP; the polling helper then
        # waits for Langfuse's worker pipeline to materialise the
        # trace as queryable.
        provider.force_flush(timeout_millis=10_000)
        await _wait_for_traces(
            apps=candidate_apps + baseline_apps,
            adapter=trace_query_port,
            tenant_context=wiring.tenant_context,
            timeout_seconds=poll_timeout_seconds,
        )

        if baseline_revision_id is None:
            cost_result = await cost_per_successful_task(
                tenant_context=wiring.tenant_context,
                scoring_sheet_revision_id=candidate_revision_id,
                interaction_set_id=interaction_set_id,
                scoring_sheet_repository=sheet_repo,
                rubric_application_repository=rubric_repo,
                cost_query_port=cost_query_adapter,
            )
            return _render_cost_result(
                cost_result=cost_result,
                output_format=output_format,
                candidate_revision_id=candidate_revision_id,
                interaction_set_id=interaction_set_id,
            )

        report = await compare_runs(
            tenant_context=wiring.tenant_context,
            baseline_revision_id=baseline_revision_id,
            candidate_revision_id=candidate_revision_id,
            interaction_set_id=interaction_set_id,
            scoring_sheet_repository=sheet_repo,
            rubric_application_repository=rubric_repo,
            cost_query_port=cost_query_adapter,
        )
        return _render_regression_report(
            report=report, output_format=output_format
        )
    finally:
        await trace_query_port.aclose()
        await wiring.engine.dispose()


async def run_report(
    *,
    tenant_id: str,
    baseline_revision_id: UUID,
    candidate_revision_id: UUID,
    interaction_set_id: UUID,
    output_format: str,
) -> str:
    wiring = build_tenant_wiring(tenant_id)
    trace_query_port = LangfuseHTTPTraceQueryAdapter()

    sheet_repo = PostgresScoringSheetRepository(wiring.session_factory)
    rubric_repo = PostgresRubricApplicationRepository(wiring.session_factory)
    cost_query_adapter = CostQueryAdapter(trace_query_port=trace_query_port)

    try:
        report = await compare_runs(
            tenant_context=wiring.tenant_context,
            baseline_revision_id=baseline_revision_id,
            candidate_revision_id=candidate_revision_id,
            interaction_set_id=interaction_set_id,
            scoring_sheet_repository=sheet_repo,
            rubric_application_repository=rubric_repo,
            cost_query_port=cost_query_adapter,
        )
        return _render_regression_report(
            report=report, output_format=output_format
        )
    finally:
        await trace_query_port.aclose()
        await wiring.engine.dispose()


async def _wait_for_traces(
    *,
    apps: list[RubricApplication],
    adapter: LangfuseHTTPTraceQueryAdapter,
    tenant_context,
    timeout_seconds: float,
) -> None:
    """Poll the trace store until each unique trace_id is available
    or the per-trace timeout elapses.

    Traces that time out individually are not fatal — the cost-query
    path's structural-absence contract counts them as ``excluded``,
    and the regression report's CriterionDelta surfaces the same
    exclusion through the ``excluded_count`` field on the underlying
    CostPerSuccessfulTaskResult.
    """
    unique = sorted(
        {app.trace_id for app in apps if app.trace_id}
    )
    for trace_id in unique:
        await adapter.wait_for_trace_availability(
            trace_id,
            tenant_context,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=1.0,
        )


def _render_cost_result(
    *,
    cost_result: CostPerSuccessfulTaskResult,
    output_format: str,
    candidate_revision_id: UUID,
    interaction_set_id: UUID,
) -> str:
    """Render a single-run cost summary.

    No regression report when there's no baseline; the operator's
    answer at this branch is the cost-per-task rollup plus
    diagnostic fields.
    """
    if output_format == _OUTPUT_FORMAT_JSON:
        import json

        return json.dumps(
            {
                "candidate_revision_id": str(candidate_revision_id),
                "interaction_set_id": str(interaction_set_id),
                "successful_count": cost_result.successful_count,
                "total_cost_usd": str(cost_result.total_cost_usd),
                "cost_per_task_usd": str(cost_result.cost_per_task_usd),
                "excluded_count": cost_result.excluded_count,
            },
            indent=2,
        )
    lines = [
        "# Eval run summary",
        "",
        f"Candidate revision: `{candidate_revision_id}`",
        f"Interaction set: `{interaction_set_id}`",
        "",
        "## Cost",
        "",
        f"- Successful applications: {cost_result.successful_count}",
        f"- Total cost: ${cost_result.total_cost_usd:.6f} USD",
        f"- Cost per successful task: ${cost_result.cost_per_task_usd:.6f} USD",
        f"- Excluded (no trace_id or no cost data): {cost_result.excluded_count}",
    ]
    return "\n".join(lines) + "\n"


def _render_regression_report(
    *,
    report: RegressionReport,
    output_format: str,
) -> str:
    if output_format == _OUTPUT_FORMAT_JSON:
        return render_json(report)
    return render_text(report)
