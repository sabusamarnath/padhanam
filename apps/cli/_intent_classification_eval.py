"""Intent-classification evaluation CLI orchestration (D137, S48b).

Single typer sub-app ``intent-classification-eval`` with three
subcommands per D137 Option B:

- ``eval start`` — kick off an evaluation run against a model on
  a named gold set; block until completion or failure; emit per-class
  accuracy summary on stdout.
- ``eval get`` — display run status, per-entry results, and per-class
  aggregates for a recorded run.
- ``eval list`` — paginated index of recent runs in a tenant.

Cross-run comparison (``compare run-ids``) defers per D137 alternative
(d) at the routine-comparison-workflow activation trigger.

The runner consumes ``StructuredOutputPort`` directly (not the cell)
per Surface 8's component-isolation discipline. The LiteLLM adapter
implements the port; D133's model registry is consulted via the
``--model`` parameter that maps to one of the registered model names.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID

import typer

from apps.cli._runtime import build_tenant_wiring
from contexts.audit.adapters.outbound.postgres.audit import PostgresAuditAdapter
from contexts.inference.adapters.outbound.litellm import LiteLLMAdapter
from contexts.intent_classification_evaluation.adapters.outbound.fixture.yaml_gold_set_reader import (
    YamlGoldSetReader,
)
from contexts.intent_classification_evaluation.adapters.outbound.postgres.reader import (
    PostgresEvaluationRunReader,
)
from contexts.intent_classification_evaluation.adapters.outbound.postgres.repository import (
    PostgresEvaluationRunRepository,
)
from contexts.intent_classification_evaluation.application.get_evaluation_run import (
    get_evaluation_run,
)
from contexts.intent_classification_evaluation.application.list_evaluation_runs import (
    list_evaluation_runs,
)
from contexts.intent_classification_evaluation.application.run_intent_classification_evaluation import (
    RunIntentClassificationEvaluationCommand,
    run_intent_classification_evaluation,
)
from padhanam.config import ControlPlaneSettings, InferenceSettings
from shared_kernel import ActorContext, LatencyTier, TenantId


intent_classification_eval_app = typer.Typer(
    name="eval",
    help=(
        "Intent-classification evaluation: gold-set-based per-model "
        "accuracy measurement. Component-quality substrate distinct from "
        "integration smokes."
    ),
)


_DEFAULT_GOLD_SET_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "tests"
    / "fixtures"
    / "intent_classification"
    / "gold_set.yaml"
)


def _build_dependencies(wiring):
    """Construct repository, reader, audit adapter, fixture reader."""
    bound_tenant_id = TenantId(str(wiring.tenant_context.tenant_id))

    async def _resolver(_tid):
        return wiring.session_factory

    repo = PostgresEvaluationRunRepository(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    reader = PostgresEvaluationRunReader(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    audit_adapter = PostgresAuditAdapter.from_settings(
        control_plane_settings=ControlPlaneSettings(),
        per_tenant_sessionmaker_resolver=_resolver,
    )
    gold_set_reader = YamlGoldSetReader(path=_DEFAULT_GOLD_SET_PATH)
    return repo, reader, audit_adapter, gold_set_reader


@intent_classification_eval_app.command("start")
def cmd_eval_start(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label ('a', 'b') or UUID.")
    ],
    model: Annotated[
        str,
        typer.Option(
            "--model",
            help=(
                "Model identifier from the registry "
                "(qwen2.5:7b, qwen2.5:14b, gpt-4o-mini)."
            ),
        ),
    ],
    gold_set_name: Annotated[
        str,
        typer.Option(
            "--gold-set-name",
            help="Gold set to evaluate against.",
        ),
    ] = "phase_2_a_default",
    invoked_by: Annotated[
        str,
        typer.Option(
            "--invoked-by",
            help="Actor for the audit trail.",
        ),
    ] = "cli-operator",
) -> None:
    """Run an intent-classification evaluation and print the per-class summary."""
    wiring = build_tenant_wiring(tenant_id)
    repo, reader, audit_adapter, gold_set_reader = _build_dependencies(wiring)
    inference_settings = InferenceSettings()
    inference_adapter = LiteLLMAdapter(settings=inference_settings)

    async def _go() -> None:
        actor = ActorContext(
            tenant_context=wiring.tenant_context,
            actor_id=invoked_by,
            role_list=frozenset({"operator"}),
            authorisation_set=frozenset({"intent_classification_evaluation"}),
        )
        try:
            result = await run_intent_classification_evaluation(
                RunIntentClassificationEvaluationCommand(
                    gold_set_name=gold_set_name,
                    model=model,
                    latency_tier=LatencyTier.REAL_TIME_REQUIRED,
                ),
                gold_set_reader=gold_set_reader,
                structured_output_port=inference_adapter,
                repository=repo,
                audit_port=audit_adapter,
                tenant=wiring.tenant_context,
                actor=actor,
            )
            typer.echo(f"evaluation_run_id={result.run_id}")
            typer.echo(f"status={result.status.value}")
            typer.echo(f"model={model}")
            typer.echo(f"gold_set_name={gold_set_name}")
            typer.echo(f"total_entries={result.total_entries}")
            typer.echo(f"correct_count={result.correct_count}")
            typer.echo(f"parse_failure_count={result.parse_failure_count}")
            if result.total_entries > 0:
                accuracy = result.correct_count / result.total_entries
                typer.echo(f"overall_accuracy={accuracy:.4f}")

            # Per-class summary
            detail = await get_evaluation_run(
                result.run_id, reader=reader, tenant=wiring.tenant_context
            )
            if detail is not None:
                typer.echo("per_class:")
                for agg in detail.aggregates:
                    typer.echo(
                        f"  {agg.intent_class}: support={agg.support} "
                        f"correct={agg.correct_count} "
                        f"accuracy={agg.accuracy:.4f} "
                        f"precision={agg.precision:.4f} "
                        f"parse_failures={agg.parse_failure_count}"
                    )
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


@intent_classification_eval_app.command("get")
def cmd_eval_get(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    run_id: Annotated[
        UUID, typer.Option("--run-id", help="Evaluation run to display.")
    ],
) -> None:
    """Show run aggregate plus per-entry results plus per-class aggregates."""
    wiring = build_tenant_wiring(tenant_id)
    _repo, reader, audit_adapter, _gold_set_reader = _build_dependencies(wiring)

    async def _go() -> None:
        try:
            detail = await get_evaluation_run(
                run_id, reader=reader, tenant=wiring.tenant_context
            )
            if detail is None:
                typer.echo(f"error: run {run_id} not found", err=True)
                raise typer.Exit(code=2)
            typer.echo(f"evaluation_run_id={detail.run.id}")
            typer.echo(f"status={detail.run.status.value}")
            typer.echo(f"gold_set_name={detail.run.gold_set_name}")
            typer.echo(
                f"model={detail.run.model_identifier.provider.value}/"
                f"{detail.run.model_identifier.version}"
            )
            typer.echo(f"started_at={detail.run.started_at.isoformat()}")
            if detail.run.completed_at is not None:
                typer.echo(
                    f"completed_at={detail.run.completed_at.isoformat()}"
                )
            if detail.run.failure_reason:
                typer.echo(f"failure_reason={detail.run.failure_reason}")
            typer.echo(f"results={len(detail.results)}")
            typer.echo("per_class:")
            for agg in detail.aggregates:
                typer.echo(
                    f"  {agg.intent_class}: support={agg.support} "
                    f"correct={agg.correct_count} "
                    f"accuracy={agg.accuracy:.4f} "
                    f"precision={agg.precision:.4f} "
                    f"parse_failures={agg.parse_failure_count}"
                )
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


@intent_classification_eval_app.command("list")
def cmd_eval_list(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    limit: Annotated[
        int, typer.Option("--limit", help="Max runs to show.")
    ] = 20,
) -> None:
    """Show recent evaluation runs, newest first."""
    wiring = build_tenant_wiring(tenant_id)
    _repo, reader, audit_adapter, _gold_set_reader = _build_dependencies(wiring)

    async def _go() -> None:
        try:
            runs = await list_evaluation_runs(
                reader=reader,
                tenant=wiring.tenant_context,
                limit=limit,
            )
            typer.echo(f"runs={len(runs)}")
            for run in runs:
                typer.echo(
                    f"  {run.id} status={run.status.value} "
                    f"model={run.model_identifier.version} "
                    f"gold_set={run.gold_set_name} "
                    f"started_at={run.started_at.isoformat()}"
                )
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


__all__ = ["intent_classification_eval_app"]
