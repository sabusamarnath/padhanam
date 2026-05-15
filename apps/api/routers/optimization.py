"""HTTP routes for the optimization surface (D112, S42).

Two FastAPI routers under the flat-module convention:

- ``optimization_run_router`` — engine kickoff plus read surface for
  the run aggregate (POST /optimization-runs synchronous per
  Finding 3, GET /optimization-runs, GET /optimization-runs/{id}).
  The kickoff route wires every default rule from
  ``contexts.optimization.application.rules.default_rules`` against an
  ``EvidenceContext`` constructed from the four producer-context
  reader ports pulled from app.state.

- ``recommendation_router`` — read surface and lifecycle write routes
  for the Recommendation aggregate (GET /recommendations,
  GET /recommendations/{id}, POST /recommendations/{id}/acknowledge,
  POST /recommendations/{id}/apply, POST /recommendations/{id}/reject).
  The lifecycle routes thread principal.subject as actor; the request
  body is empty for the three transition routes.

Tenancy resolves via the shared ``get_tenant_context`` dependency at
``apps/api/routers/inference.py`` per the S15 / S37 hardening pattern.
Cross-tenant access returns 404 with no information leakage in error
bodies. Platform-operator-typed tokens are rejected with 403
``principal_type_mismatch`` per D103/D104.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api._errors import OptimizationRunNotFoundError
from apps.api.middleware import get_principal
from apps.api.routers._optimization_dto import (
    OptimizationRunListResponse,
    OptimizationRunResponse,
    RecommendationListResponse,
    RecommendationResponse,
    RecommendationStatusTransitionResponse,
    StartOptimizationRunResponse,
    TransitionResponse,
)
from apps.api.routers._optimization_query import (
    parse_optimization_run_list_query,
    parse_recommendation_list_query,
)
from apps.api.routers.inference import get_tenant_context
from contexts.audit.domain.ports import AuditPort
from contexts.audit.ports.reader import AuditEventReader
from contexts.optimization.application import (
    EvidenceContext,
    RecommendationNotFoundError,
    acknowledge_recommendation,
    apply_recommendation,
    get_optimization_run,
    get_recommendation,
    list_optimization_runs,
    list_recommendations,
    reject_recommendation,
    run_optimization,
)
from contexts.optimization.application.rules import default_rules
from contexts.optimization.domain.query_filters import (
    RecommendationListFilters,
)
from contexts.optimization.ports.optimization_run_reader import (
    OptimizationRunReader,
)
from contexts.optimization.ports.optimization_run_repository import (
    OptimizationRunRepository,
)
from contexts.optimization.ports.recommendation_reader import (
    RecommendationReader,
)
from contexts.optimization.ports.recommendation_repository import (
    RecommendationRepository,
)
from contexts.retrieval_evaluation.ports.evaluation_run_reader import (
    EvaluationRunReader,
)
from contexts.retrieval_evaluation.ports.reader import GoldSetReader
from contexts.run_history.ports.reader import RunHistoryReader
from padhanam.security import Principal
from shared_kernel import TenantContext


# ---------------------------------------------------------------------------
# Router definitions
# ---------------------------------------------------------------------------


optimization_run_router = APIRouter(
    prefix="/optimization-runs",
    tags=["optimization", "runs"],
)
recommendation_router = APIRouter(
    prefix="/recommendations",
    tags=["optimization", "recommendations"],
)


# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------


def get_optimization_run_repository(
    request: Request,
) -> OptimizationRunRepository:
    repo = getattr(request.app.state, "optimization_run_repository", None)
    if repo is None:
        raise HTTPException(
            status_code=503,
            detail="optimization-run repository not configured on this API instance",
        )
    return repo


def get_optimization_run_reader(request: Request) -> OptimizationRunReader:
    reader = getattr(request.app.state, "optimization_run_reader", None)
    if reader is None:
        raise HTTPException(
            status_code=503,
            detail="optimization-run reader not configured on this API instance",
        )
    return reader


def get_recommendation_repository(
    request: Request,
) -> RecommendationRepository:
    repo = getattr(request.app.state, "recommendation_repository", None)
    if repo is None:
        raise HTTPException(
            status_code=503,
            detail="recommendation repository not configured on this API instance",
        )
    return repo


def get_recommendation_reader(request: Request) -> RecommendationReader:
    reader = getattr(request.app.state, "recommendation_reader", None)
    if reader is None:
        raise HTTPException(
            status_code=503,
            detail="recommendation reader not configured on this API instance",
        )
    return reader


def get_audit_port(request: Request) -> AuditPort:
    audit = getattr(request.app.state, "audit_port", None)
    if audit is None:
        raise HTTPException(
            status_code=503,
            detail="audit port not configured on this API instance",
        )
    return audit


def get_evaluation_run_reader_for_evidence(
    request: Request,
) -> EvaluationRunReader:
    reader = getattr(request.app.state, "evaluation_run_reader", None)
    if reader is None:
        raise HTTPException(
            status_code=503,
            detail="evaluation-run reader not configured on this API instance",
        )
    return reader


def get_gold_set_reader_for_evidence(request: Request) -> GoldSetReader:
    reader = getattr(request.app.state, "gold_set_reader", None)
    if reader is None:
        raise HTTPException(
            status_code=503,
            detail="gold-set reader not configured on this API instance",
        )
    return reader


def get_run_history_reader_for_evidence(request: Request) -> RunHistoryReader:
    reader = getattr(request.app.state, "run_history_reader", None)
    if reader is None:
        raise HTTPException(
            status_code=503,
            detail="run-history reader not configured on this API instance",
        )
    return reader


def get_audit_event_reader_for_evidence(request: Request) -> AuditEventReader:
    reader = getattr(request.app.state, "audit_event_reader", None)
    if reader is None:
        raise HTTPException(
            status_code=503,
            detail="audit-event reader not configured on this API instance",
        )
    return reader


# ---------------------------------------------------------------------------
# Optimization runs
# ---------------------------------------------------------------------------


@optimization_run_router.post(
    "",
    response_model=StartOptimizationRunResponse,
    operation_id="startOptimizationRun",
    status_code=201,
)
async def start_optimization_run_route(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    principal: Annotated[Principal, Depends(get_principal)],
    run_repository: Annotated[
        OptimizationRunRepository, Depends(get_optimization_run_repository)
    ],
    recommendation_repository: Annotated[
        RecommendationRepository, Depends(get_recommendation_repository)
    ],
    audit_port: Annotated[AuditPort, Depends(get_audit_port)],
    evaluation_run_reader: Annotated[
        EvaluationRunReader, Depends(get_evaluation_run_reader_for_evidence)
    ],
    gold_set_reader: Annotated[
        GoldSetReader, Depends(get_gold_set_reader_for_evidence)
    ],
    run_history_reader: Annotated[
        RunHistoryReader, Depends(get_run_history_reader_for_evidence)
    ],
    audit_event_reader: Annotated[
        AuditEventReader, Depends(get_audit_event_reader_for_evidence)
    ],
) -> StartOptimizationRunResponse:
    """Synchronous engine kickoff per Finding 3 / D112 commitment 4.

    Iterates the four default rules per D111 commitment 5 against
    evidence pulled from the four producer-context reader ports.
    Zero-recommendation rules (model_choice, prompt_revision) record
    structured ``CategorySkipReason`` entries on the run aggregate's
    ``skipped_categories`` field; the response carries them embedded.
    """
    evidence_context = EvidenceContext(
        tenant_context=tenant_context,
        evaluation_run_reader=evaluation_run_reader,
        run_history_reader=run_history_reader,
        gold_set_reader=gold_set_reader,
        audit_event_reader=audit_event_reader,
    )
    result = await run_optimization(
        tenant_context=tenant_context,
        invoked_by_user_id=principal.subject,
        rules=default_rules(),
        evidence_context=evidence_context,
        optimization_run_repository=run_repository,
        recommendation_repository=recommendation_repository,
        audit_port=audit_port,
    )
    return StartOptimizationRunResponse(
        run=OptimizationRunResponse.model_validate(result.run),
        recommendations=[
            RecommendationResponse.model_validate(r)
            for r in result.recommendations
        ],
    )


@optimization_run_router.get(
    "",
    response_model=OptimizationRunListResponse,
    operation_id="listOptimizationRuns",
)
async def list_optimization_runs_route(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[
        OptimizationRunReader, Depends(get_optimization_run_reader)
    ],
    query: Annotated[
        tuple[str | None, int], Depends(parse_optimization_run_list_query)
    ],
) -> OptimizationRunListResponse:
    cursor, page_size = query
    page, next_cursor = await list_optimization_runs(
        tenant_context=tenant_context,
        reader=reader,
        encoded_cursor=cursor,
        page_size=page_size,
    )
    return OptimizationRunListResponse(
        items=[OptimizationRunResponse.model_validate(r) for r in page.runs],
        next_cursor=next_cursor,
    )


@optimization_run_router.get(
    "/{run_id}",
    response_model=OptimizationRunResponse,
    operation_id="getOptimizationRun",
)
async def get_optimization_run_route(
    run_id: UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[
        OptimizationRunReader, Depends(get_optimization_run_reader)
    ],
) -> OptimizationRunResponse:
    snapshot = await get_optimization_run(
        tenant_context=tenant_context,
        run_id=run_id,
        reader=reader,
    )
    if snapshot is None:
        raise OptimizationRunNotFoundError(str(run_id))
    return OptimizationRunResponse.model_validate(snapshot.run)


# ---------------------------------------------------------------------------
# Recommendations — read
# ---------------------------------------------------------------------------


@recommendation_router.get(
    "",
    response_model=RecommendationListResponse,
    operation_id="listRecommendations",
)
async def list_recommendations_route(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[RecommendationReader, Depends(get_recommendation_reader)],
    query: Annotated[
        tuple[RecommendationListFilters, str | None, int],
        Depends(parse_recommendation_list_query),
    ],
) -> RecommendationListResponse:
    filters, cursor, page_size = query
    page, next_cursor = await list_recommendations(
        tenant_context=tenant_context,
        reader=reader,
        filters=filters,
        encoded_cursor=cursor,
        page_size=page_size,
    )
    return RecommendationListResponse(
        items=[
            RecommendationResponse.model_validate(r)
            for r in page.recommendations
        ],
        next_cursor=next_cursor,
    )


@recommendation_router.get(
    "/{recommendation_id}",
    response_model=RecommendationResponse,
    operation_id="getRecommendation",
)
async def get_recommendation_route(
    recommendation_id: UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[RecommendationReader, Depends(get_recommendation_reader)],
) -> RecommendationResponse:
    recommendation = await get_recommendation(
        tenant_context=tenant_context,
        recommendation_id=recommendation_id,
        reader=reader,
    )
    if recommendation is None:
        raise RecommendationNotFoundError(
            f"recommendation {recommendation_id} not found for tenant"
        )
    return RecommendationResponse.model_validate(recommendation)


# ---------------------------------------------------------------------------
# Recommendations — lifecycle (acknowledge / apply / reject)
# ---------------------------------------------------------------------------


def _build_transition_response(result) -> TransitionResponse:
    return TransitionResponse(
        recommendation=RecommendationResponse.model_validate(result.recommendation),
        transition=RecommendationStatusTransitionResponse.model_validate(
            result.transition
        ),
    )


@recommendation_router.post(
    "/{recommendation_id}/acknowledge",
    response_model=TransitionResponse,
    operation_id="acknowledgeRecommendation",
)
async def acknowledge_recommendation_route(
    recommendation_id: UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    principal: Annotated[Principal, Depends(get_principal)],
    reader: Annotated[RecommendationReader, Depends(get_recommendation_reader)],
    repository: Annotated[
        RecommendationRepository, Depends(get_recommendation_repository)
    ],
    audit_port: Annotated[AuditPort, Depends(get_audit_port)],
) -> TransitionResponse:
    result = await acknowledge_recommendation(
        tenant_context=tenant_context,
        recommendation_id=recommendation_id,
        actor_user_id=principal.subject,
        reader=reader,
        repository=repository,
        audit_port=audit_port,
    )
    return _build_transition_response(result)


@recommendation_router.post(
    "/{recommendation_id}/apply",
    response_model=TransitionResponse,
    operation_id="applyRecommendation",
)
async def apply_recommendation_route(
    recommendation_id: UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    principal: Annotated[Principal, Depends(get_principal)],
    reader: Annotated[RecommendationReader, Depends(get_recommendation_reader)],
    repository: Annotated[
        RecommendationRepository, Depends(get_recommendation_repository)
    ],
    audit_port: Annotated[AuditPort, Depends(get_audit_port)],
) -> TransitionResponse:
    result = await apply_recommendation(
        tenant_context=tenant_context,
        recommendation_id=recommendation_id,
        actor_user_id=principal.subject,
        reader=reader,
        repository=repository,
        audit_port=audit_port,
    )
    return _build_transition_response(result)


@recommendation_router.post(
    "/{recommendation_id}/reject",
    response_model=TransitionResponse,
    operation_id="rejectRecommendation",
)
async def reject_recommendation_route(
    recommendation_id: UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    principal: Annotated[Principal, Depends(get_principal)],
    reader: Annotated[RecommendationReader, Depends(get_recommendation_reader)],
    repository: Annotated[
        RecommendationRepository, Depends(get_recommendation_repository)
    ],
    audit_port: Annotated[AuditPort, Depends(get_audit_port)],
) -> TransitionResponse:
    result = await reject_recommendation(
        tenant_context=tenant_context,
        recommendation_id=recommendation_id,
        actor_user_id=principal.subject,
        reader=reader,
        repository=repository,
        audit_port=audit_port,
    )
    return _build_transition_response(result)


__all__ = [
    "get_audit_event_reader_for_evidence",
    "get_audit_port",
    "get_evaluation_run_reader_for_evidence",
    "get_gold_set_reader_for_evidence",
    "get_optimization_run_reader",
    "get_optimization_run_repository",
    "get_recommendation_reader",
    "get_recommendation_repository",
    "get_run_history_reader_for_evidence",
    "optimization_run_router",
    "recommendation_router",
]
