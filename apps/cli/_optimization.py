"""Optimization CLI orchestration (S41 / D111).

Two typer sub-apps:

- ``optimization`` (S41): engine + lifecycle + reads — run, get,
  list, acknowledge, apply, reject.
- ``optimization-run`` (S41): read-side surface for the engine
  invocation aggregate — get, list.

The ``optimization run`` subcommand wires the engine against the
four producer-context reader ports plus the optimization-context
repositories and audit adapter, then iterates the four default
rules per D111 commitment 5. Phase 1 zero rules (model_choice and
prompt_revision) surface as ``skipped_categories`` entries on the
parent OptimizationRun aggregate; the CLI renders them in the run
summary for procurement-grade transparency.

Tenant context resolution uses ``build_tenant_wiring`` per the
dev-only label-or-UUID convention. The control-plane audit reader
session anchor mirrors the PostgresAuditAdapter's control-plane
session pattern (S37).
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Optional
from uuid import UUID

import typer

from contexts.audit.adapters.outbound.postgres.audit import PostgresAuditAdapter
from contexts.audit.adapters.outbound.postgres.reader import (
    PostgresAuditEventReader,
)
from contexts.optimization.adapters.outbound.postgres.optimization_run_reader import (
    PostgresOptimizationRunReader,
)
from contexts.optimization.adapters.outbound.postgres.optimization_run_repository import (
    PostgresOptimizationRunRepository,
)
from contexts.optimization.adapters.outbound.postgres.recommendation_reader import (
    PostgresRecommendationReader,
)
from contexts.optimization.adapters.outbound.postgres.recommendation_repository import (
    PostgresRecommendationRepository,
)
from contexts.matcher_policy.adapters.outbound.postgres import (
    PostgresMatcherPolicyRepository,
)
from contexts.optimization.application import (
    EvidenceContext,
    RecommendationNotFoundError,
    TransitionNotPermittedError,
    acknowledge_recommendation,
    apply_matcher_suppression,
    apply_recommendation,
    revert_matcher_suppression,
    get_optimization_run,
    get_recommendation,
    list_optimization_runs,
    list_recommendations,
    reject_recommendation,
    run_optimization,
)
from contexts.optimization.application.rules import default_rules
from contexts.optimization.domain import (
    Recommendation,
    RecommendationCategory,
    RecommendationStatus,
)
from contexts.matcher_evaluation.adapters.outbound.postgres import (
    PostgresMatcherQualityRunReader,
)
from contexts.optimization.domain.query_filters import (
    RecommendationListFilters,
)
from contexts.retrieval_evaluation.adapters.outbound.postgres.evaluation_run_reader import (
    PostgresEvaluationRunReader,
)
from contexts.retrieval_evaluation.adapters.outbound.postgres.reader import (
    PostgresGoldSetReader,
)
from contexts.run_history.adapters.outbound.postgres import (
    PostgresRunHistoryReader,
)
from padhanam.config import ControlPlaneSettings
from shared_kernel import TenantId

from apps.cli._runtime import build_tenant_wiring


optimization_app = typer.Typer(
    name="optimization",
    help="Optimization engine + lifecycle (S41 / D111).",
    no_args_is_help=True,
)

optimization_run_app = typer.Typer(
    name="optimization-run",
    help="Optimization-run read surface (S41 / D111).",
    no_args_is_help=True,
)


# ----------------------------------------------------------------------
# Dependency wiring
# ----------------------------------------------------------------------


def _build_dependencies(wiring):
    """Construct every adapter the engine + lifecycle commands need."""
    bound_tenant_id = TenantId(str(wiring.tenant_context.tenant_id))

    async def _resolver(_tid):
        return wiring.session_factory

    run_repo = PostgresOptimizationRunRepository(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    run_reader = PostgresOptimizationRunReader(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    rec_repo = PostgresRecommendationRepository(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    rec_reader = PostgresRecommendationReader(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )

    audit_adapter = PostgresAuditAdapter.from_settings(
        control_plane_settings=ControlPlaneSettings(),
        per_tenant_sessionmaker_resolver=_resolver,
    )

    audit_event_reader = PostgresAuditEventReader(
        per_tenant_sessionmaker_resolver=_resolver,
        control_plane_sessionmaker=audit_adapter.control_plane_sessionmaker,
    )

    evaluation_run_reader = PostgresEvaluationRunReader(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    gold_set_reader = PostgresGoldSetReader(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    run_history_reader = PostgresRunHistoryReader(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )

    matcher_quality_run_reader = PostgresMatcherQualityRunReader(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )

    evidence_context = EvidenceContext(
        tenant_context=wiring.tenant_context,
        evaluation_run_reader=evaluation_run_reader,
        run_history_reader=run_history_reader,
        gold_set_reader=gold_set_reader,
        audit_event_reader=audit_event_reader,
        matcher_quality_run_reader=matcher_quality_run_reader,
    )

    return (
        run_repo,
        run_reader,
        rec_repo,
        rec_reader,
        audit_adapter,
        evidence_context,
    )


# ----------------------------------------------------------------------
# Rendering helpers
# ----------------------------------------------------------------------


def _render_recommendation(recommendation: Recommendation) -> None:
    typer.echo(f"id={recommendation.id}")
    typer.echo(f"category={recommendation.category.value}")
    typer.echo(f"status={recommendation.status.value}")
    typer.echo(f"subject={recommendation.subject}")
    typer.echo(f"generated_at={recommendation.generated_at.isoformat()}")
    typer.echo(f"generated_by_run_id={recommendation.generated_by_run_id}")
    typer.echo(
        f"last_transition_at="
        f"{recommendation.last_transition_at.isoformat()}"
    )
    typer.echo(
        "last_transition_by_user_id="
        f"{recommendation.last_transition_by_user_id or '(none)'}"
    )
    typer.echo(f"text: {recommendation.text}")
    typer.echo(f"evidence_citations: {len(recommendation.evidence_citations)}")
    for index, citation in enumerate(recommendation.evidence_citations, 1):
        typer.echo(f"  citation {index}: {citation}")


# ----------------------------------------------------------------------
# optimization run
# ----------------------------------------------------------------------


@optimization_app.command("run")
def cmd_optimization_run(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    invoked_by: Annotated[
        str,
        typer.Option(
            "--invoked-by",
            help="Invocation actor for the audit trail.",
        ),
    ] = "cli-operator",
) -> None:
    """Run the optimization engine against the named tenant's evidence."""
    wiring = build_tenant_wiring(tenant_id)
    (
        run_repo,
        _run_reader,
        rec_repo,
        _rec_reader,
        audit_adapter,
        evidence_context,
    ) = _build_dependencies(wiring)

    async def _go() -> None:
        try:
            result = await run_optimization(
                tenant_context=wiring.tenant_context,
                invoked_by_user_id=invoked_by,
                rules=default_rules(),
                evidence_context=evidence_context,
                optimization_run_repository=run_repo,
                recommendation_repository=rec_repo,
                audit_port=audit_adapter,
            )
            typer.echo(f"optimization_run_id={result.run.id}")
            typer.echo(f"status={result.run.status.value}")
            typer.echo(
                f"completed_at={result.run.completed_at.isoformat() if result.run.completed_at else '(none)'}"
            )
            typer.echo(f"recommendations_generated={len(result.recommendations)}")
            counts_by_category: dict[str, int] = {}
            for rec in result.recommendations:
                counts_by_category[rec.category.value] = (
                    counts_by_category.get(rec.category.value, 0) + 1
                )
            for category in (c.value for c in RecommendationCategory):
                count = counts_by_category.get(category, 0)
                skip = result.skipped_categories.get(category)
                if skip is not None:
                    typer.echo(
                        f"  {category}: 0 (skipped; "
                        f"reason_code={skip.reason_code}) "
                        f"reason: {skip.reason_text}"
                    )
                else:
                    typer.echo(f"  {category}: {count}")
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


# ----------------------------------------------------------------------
# optimization get / list
# ----------------------------------------------------------------------


@optimization_app.command("get")
def cmd_optimization_get(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    recommendation_id: Annotated[
        UUID,
        typer.Option(
            "--recommendation-id", help="Recommendation UUID to fetch."
        ),
    ],
) -> None:
    """Get a single recommendation with full citation rendering."""
    wiring = build_tenant_wiring(tenant_id)
    _, _, _, rec_reader, audit_adapter, _ = _build_dependencies(wiring)

    async def _go() -> None:
        try:
            recommendation = await get_recommendation(
                tenant_context=wiring.tenant_context,
                recommendation_id=recommendation_id,
                reader=rec_reader,
            )
            if recommendation is None:
                typer.echo(
                    f"recommendation {recommendation_id} not found", err=True
                )
                raise typer.Exit(code=2)
            _render_recommendation(recommendation)
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


@optimization_app.command("list")
def cmd_optimization_list(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    category: Annotated[
        Optional[str],
        typer.Option(
            "--category",
            help="Filter by category (retrieval_strategy / model_choice / "
            "prompt_revision / cost_optimization).",
        ),
    ] = None,
    status: Annotated[
        Optional[str],
        typer.Option(
            "--status",
            help="Filter by status (generated / acknowledged / applied / "
            "rejected).",
        ),
    ] = None,
    page_size: Annotated[
        int, typer.Option("--page-size", help="Page size (1-50).")
    ] = 20,
) -> None:
    """List recommendations, filtered by category and/or status."""
    wiring = build_tenant_wiring(tenant_id)
    _, _, _, rec_reader, audit_adapter, _ = _build_dependencies(wiring)

    categories = (
        (RecommendationCategory(category),) if category else None
    )
    statuses = (RecommendationStatus(status),) if status else None
    filters = RecommendationListFilters(
        categories=categories, statuses=statuses
    )

    async def _go() -> None:
        try:
            page, next_cursor = await list_recommendations(
                tenant_context=wiring.tenant_context,
                reader=rec_reader,
                filters=filters,
                encoded_cursor=None,
                page_size=page_size,
            )
            typer.echo(f"recommendations: {len(page.recommendations)}")
            for rec in page.recommendations:
                typer.echo(
                    f"  {rec.id} | {rec.category.value} | "
                    f"{rec.status.value} | {rec.subject}"
                )
            if next_cursor is not None:
                typer.echo(f"next_cursor={next_cursor}")
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


# ----------------------------------------------------------------------
# optimization acknowledge / apply / reject
# ----------------------------------------------------------------------


def _lifecycle_cmd(
    tenant_id: str,
    recommendation_id: UUID,
    actor: str,
    callable_,
    verb: str,
) -> None:
    wiring = build_tenant_wiring(tenant_id)
    _, _, rec_repo, rec_reader, audit_adapter, _ = _build_dependencies(
        wiring
    )

    async def _go() -> None:
        try:
            try:
                result = await callable_(
                    tenant_context=wiring.tenant_context,
                    recommendation_id=recommendation_id,
                    actor_user_id=actor,
                    reader=rec_reader,
                    repository=rec_repo,
                    audit_port=audit_adapter,
                )
            except RecommendationNotFoundError as exc:
                typer.echo(f"error: {exc}", err=True)
                raise typer.Exit(code=2)
            except TransitionNotPermittedError as exc:
                typer.echo(f"error: {exc}", err=True)
                raise typer.Exit(code=3)
            typer.echo(
                f"recommendation {recommendation_id} {verb} → "
                f"{result.recommendation.status.value}"
            )
            typer.echo(f"transition_id={result.transition.id}")
            typer.echo(
                f"transitioned_at="
                f"{result.transition.transitioned_at.isoformat()}"
            )
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


@optimization_app.command("acknowledge")
def cmd_optimization_acknowledge(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    recommendation_id: Annotated[
        UUID, typer.Option("--recommendation-id", help="Recommendation UUID.")
    ],
    actor: Annotated[
        str, typer.Option("--actor", help="Acting user id.")
    ] = "cli-operator",
) -> None:
    """Acknowledge a recommendation (GENERATED → ACKNOWLEDGED)."""
    _lifecycle_cmd(
        tenant_id,
        recommendation_id,
        actor,
        acknowledge_recommendation,
        "acknowledged",
    )


@optimization_app.command("apply")
def cmd_optimization_apply(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    recommendation_id: Annotated[
        UUID, typer.Option("--recommendation-id", help="Recommendation UUID.")
    ],
    actor: Annotated[
        str, typer.Option("--actor", help="Acting user id.")
    ] = "cli-operator",
) -> None:
    """Apply a recommendation (GENERATED|ACKNOWLEDGED → APPLIED)."""
    _lifecycle_cmd(
        tenant_id,
        recommendation_id,
        actor,
        apply_recommendation,
        "applied",
    )


@optimization_app.command("apply-matcher")
def cmd_optimization_apply_matcher(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    recommendation_id: Annotated[
        UUID, typer.Option("--recommendation-id", help="Recommendation UUID.")
    ],
    actor: Annotated[
        str, typer.Option("--actor", help="Acting user id.")
    ] = "cli-operator",
) -> None:
    """Apply a matcher_suppression recommendation (D186/S91b).

    Writes the active suppress-single-signal policy to the neutral MatcherPolicy
    surface and marks the recommendation APPLIED — the platform's first automated
    apply. The matcher suppresses single-signal candidates on its next correlate
    run. This is the gated final step; run it only after the ground-truth verdict
    on the surfaced candidates (S91a).
    """
    wiring = build_tenant_wiring(tenant_id)
    _, _, rec_repo, rec_reader, audit_adapter, _ = _build_dependencies(wiring)

    async def _resolver(_tid):
        return wiring.session_factory

    policy_repository = PostgresMatcherPolicyRepository(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=TenantId(str(wiring.tenant_context.tenant_id)),
    )

    async def _go() -> None:
        try:
            try:
                applied = await apply_matcher_suppression(
                    tenant_context=wiring.tenant_context,
                    recommendation_id=recommendation_id,
                    actor_user_id=actor,
                    reader=rec_reader,
                    repository=rec_repo,
                    audit_port=audit_adapter,
                    policy_repository=policy_repository,
                )
            except RecommendationNotFoundError as exc:
                typer.echo(f"error: {exc}", err=True)
                raise typer.Exit(code=2)
            typer.echo(
                f"recommendation {recommendation_id} applied → "
                f"{applied.status.value}; suppress_single_signal policy active"
            )
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


@optimization_app.command("revert-matcher")
def cmd_optimization_revert_matcher(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
) -> None:
    """Revert matcher single-signal suppression (D186/S91b).

    Writes the suppress-single-signal policy back to false — the clean whole-rule
    revert, so the loop is not a one-way door. The matcher stops suppressing on
    its next correlate run. Idempotent. (Per-edge override is the deferred
    correction layer, not this.)
    """
    wiring = build_tenant_wiring(tenant_id)

    async def _resolver(_tid):
        return wiring.session_factory

    policy_repository = PostgresMatcherPolicyRepository(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=TenantId(str(wiring.tenant_context.tenant_id)),
    )

    async def _go() -> None:
        try:
            await revert_matcher_suppression(
                tenant_context=wiring.tenant_context,
                policy_repository=policy_repository,
            )
            typer.echo(
                "suppress_single_signal policy reverted → inactive; the matcher "
                "stops suppressing on its next run"
            )
        finally:
            await wiring.engine.dispose()

    asyncio.run(_go())


@optimization_app.command("reject")
def cmd_optimization_reject(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    recommendation_id: Annotated[
        UUID, typer.Option("--recommendation-id", help="Recommendation UUID.")
    ],
    actor: Annotated[
        str, typer.Option("--actor", help="Acting user id.")
    ] = "cli-operator",
) -> None:
    """Reject a recommendation (GENERATED|ACKNOWLEDGED → REJECTED)."""
    _lifecycle_cmd(
        tenant_id,
        recommendation_id,
        actor,
        reject_recommendation,
        "rejected",
    )


# ----------------------------------------------------------------------
# optimization-run get / list
# ----------------------------------------------------------------------


@optimization_run_app.command("get")
def cmd_optimization_run_get(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    run_id: Annotated[
        UUID, typer.Option("--run-id", help="Optimization-run UUID.")
    ],
) -> None:
    """Get a single optimization-run aggregate."""
    wiring = build_tenant_wiring(tenant_id)
    _, run_reader, _, _, audit_adapter, _ = _build_dependencies(wiring)

    async def _go() -> None:
        try:
            snapshot = await get_optimization_run(
                tenant_context=wiring.tenant_context,
                run_id=run_id,
                reader=run_reader,
            )
            if snapshot is None:
                typer.echo(f"optimization run {run_id} not found", err=True)
                raise typer.Exit(code=2)
            run = snapshot.run
            typer.echo(f"id={run.id}")
            typer.echo(f"status={run.status.value}")
            typer.echo(f"invoked_at={run.invoked_at.isoformat()}")
            typer.echo(
                "completed_at="
                f"{run.completed_at.isoformat() if run.completed_at else '(none)'}"
            )
            typer.echo(f"invoked_by_user_id={run.invoked_by_user_id}")
            typer.echo(f"skipped_categories: {len(run.skipped_categories)}")
            for category, reason in run.skipped_categories.items():
                typer.echo(
                    f"  {category}: {reason.reason_code} | {reason.reason_text}"
                )
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


@optimization_run_app.command("list")
def cmd_optimization_run_list(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    page_size: Annotated[
        int, typer.Option("--page-size", help="Page size (1-50).")
    ] = 20,
) -> None:
    """List optimization runs for the tenant (newest first)."""
    wiring = build_tenant_wiring(tenant_id)
    _, run_reader, _, _, audit_adapter, _ = _build_dependencies(wiring)

    async def _go() -> None:
        try:
            page, next_cursor = await list_optimization_runs(
                tenant_context=wiring.tenant_context,
                reader=run_reader,
                encoded_cursor=None,
                page_size=page_size,
            )
            typer.echo(f"runs: {len(page.runs)}")
            for run in page.runs:
                typer.echo(
                    f"  {run.id} | {run.status.value} | "
                    f"{run.invoked_at.isoformat()} | {run.invoked_by_user_id}"
                )
            if next_cursor is not None:
                typer.echo(f"next_cursor={next_cursor}")
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


__all__ = [
    "optimization_app",
    "optimization_run_app",
]
