"""HTTP routes for the retrieval-evaluation surface (D112, S42).

Three FastAPI routers under the flat-module convention:

- ``gold_set_router`` — gold-set authoring (POST /gold-sets, GET /gold-sets,
  GET /gold-sets/{id}, POST /gold-sets/{id}/entries,
  POST /gold-sets/{id}/finalize). Append-only writes per D109 inherited
  through to the HTTP surface; no edit or delete routes (Finding 2
  disposition / D112 alternative (h)).
- ``discovery_router`` — Stage 1 of the two-step discovery decomposition
  (GET /retrieval-candidates). Surfaces ranked candidate chunks the
  operator selects from before posting the entry; preserves the
  human-in-the-loop content-fit discipline S40b committed to as
  procurement-grade authoring (D112 commitment 1).
- ``evaluation_run_router`` — runner orchestration (POST /evaluation-runs
  synchronous per Finding 3, GET /evaluation-runs, GET /evaluation-runs/{id}).

All routes carry principal-derived tenant context per the S15 / S37
hardening pattern via the shared ``get_tenant_context`` dependency at
``apps/api/routers/inference.py``. Cross-tenant access returns 404 with
no information leakage in error bodies. Platform-operator-typed tokens
are rejected with 403 ``principal_type_mismatch`` per D103/D104.

Actor attribution (created_by_user_id / invoked_by_user_id) comes from
the JWT principal's ``subject`` claim; request bodies do not carry
actor fields.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from apps.api._errors import EvaluationRunNotFoundError
from apps.api.middleware import get_principal
from apps.api.routers._retrieval_evaluation_dto import (
    AppendEntryRequest,
    AppendEntryResponse,
    CreateGoldSetRequest,
    CreateGoldSetResponse,
    EvaluationAggregateResponse,
    EvaluationResultResponse,
    EvaluationRunListResponse,
    EvaluationRunResponse,
    EvaluationRunSnapshotResponse,
    FinalizeRevisionResponse,
    GoldSetEntryResponse,
    GoldSetListResponse,
    GoldSetResponse,
    GoldSetRevisionResponse,
    GoldSetWithRevisionResponse,
    RetrievalCandidateResponse,
    RetrievalCandidatesResponse,
    StartEvaluationRunRequest,
    StartEvaluationRunResponse,
)
from apps.api.routers._retrieval_evaluation_query import (
    parse_evaluation_run_list_query,
    parse_gold_set_list_query,
)
from apps.api.routers.inference import get_tenant_context
from contexts.audit.domain.ports import AuditPort
from contexts.retrieval_evaluation.application import (
    append_entry_to_revision,
    create_gold_set,
    finalize_revision,
    get_evaluation_run,
    get_gold_set,
    list_evaluation_runs,
    list_gold_sets,
    run_retrieval_evaluation,
)
from contexts.retrieval_evaluation.domain import BinaryRelevanceMetrics
from contexts.retrieval_evaluation.ports.evaluation_run_reader import (
    EvaluationRunReader,
)
from contexts.retrieval_evaluation.ports.evaluation_run_repository import (
    EvaluationRunRepository,
)
from contexts.retrieval_evaluation.ports.reader import GoldSetReader
from contexts.retrieval_evaluation.ports.repository import GoldSetRepository
from contexts.retrieval_evaluation.ports.retrieval_runner import (
    RetrievalRunnerPort,
)
from padhanam.security import Principal
from shared_kernel import TenantContext


# ---------------------------------------------------------------------------
# Router definitions
# ---------------------------------------------------------------------------


gold_set_router = APIRouter(
    prefix="/gold-sets",
    tags=["retrieval-evaluation", "gold-sets"],
)
discovery_router = APIRouter(
    prefix="/retrieval-candidates",
    tags=["retrieval-evaluation", "discovery"],
)
evaluation_run_router = APIRouter(
    prefix="/evaluation-runs",
    tags=["retrieval-evaluation", "evaluation-runs"],
)


# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------


def get_gold_set_repository(request: Request) -> GoldSetRepository:
    repo = getattr(request.app.state, "gold_set_repository", None)
    if repo is None:
        raise HTTPException(
            status_code=503,
            detail="gold-set repository not configured on this API instance",
        )
    return repo


def get_gold_set_reader(request: Request) -> GoldSetReader:
    reader = getattr(request.app.state, "gold_set_reader", None)
    if reader is None:
        raise HTTPException(
            status_code=503,
            detail="gold-set reader not configured on this API instance",
        )
    return reader


def get_evaluation_run_repository(
    request: Request,
) -> EvaluationRunRepository:
    repo = getattr(request.app.state, "evaluation_run_repository", None)
    if repo is None:
        raise HTTPException(
            status_code=503,
            detail="evaluation-run repository not configured on this API instance",
        )
    return repo


def get_evaluation_run_reader(request: Request) -> EvaluationRunReader:
    reader = getattr(request.app.state, "evaluation_run_reader", None)
    if reader is None:
        raise HTTPException(
            status_code=503,
            detail="evaluation-run reader not configured on this API instance",
        )
    return reader


def get_retrieval_runner_port(request: Request) -> RetrievalRunnerPort:
    runner = getattr(request.app.state, "retrieval_runner_port", None)
    if runner is None:
        raise HTTPException(
            status_code=503,
            detail="retrieval runner port not configured on this API instance",
        )
    return runner


def get_audit_port(request: Request) -> AuditPort:
    audit = getattr(request.app.state, "audit_port", None)
    if audit is None:
        raise HTTPException(
            status_code=503,
            detail="audit port not configured on this API instance",
        )
    return audit


def get_retrieval_client(request: Request):
    """Return the ``TenantRoutingRetrievalClient`` for discovery candidates."""
    client = getattr(request.app.state, "retrieval_client", None)
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="retrieval client not configured on this API instance",
        )
    return client


# ---------------------------------------------------------------------------
# Gold-set authoring
# ---------------------------------------------------------------------------


@gold_set_router.post(
    "",
    response_model=CreateGoldSetResponse,
    operation_id="createGoldSet",
    status_code=201,
)
async def create_gold_set_route(
    body: CreateGoldSetRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    principal: Annotated[Principal, Depends(get_principal)],
    repository: Annotated[GoldSetRepository, Depends(get_gold_set_repository)],
) -> CreateGoldSetResponse:
    result = await create_gold_set(
        tenant_context=tenant_context,
        name=body.name,
        created_by_user_id=principal.subject,
        repository=repository,
    )
    return CreateGoldSetResponse(
        gold_set=GoldSetResponse.model_validate(result.gold_set),
        initial_revision=GoldSetRevisionResponse.model_validate(
            result.initial_revision
        ),
    )


@gold_set_router.get(
    "",
    response_model=GoldSetListResponse,
    operation_id="listGoldSets",
)
async def list_gold_sets_route(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[GoldSetReader, Depends(get_gold_set_reader)],
    query: Annotated[
        tuple[str | None, int], Depends(parse_gold_set_list_query)
    ],
) -> GoldSetListResponse:
    cursor, page_size = query
    page, next_cursor = await list_gold_sets(
        tenant_context=tenant_context,
        reader=reader,
        encoded_cursor=cursor,
        page_size=page_size,
    )
    return GoldSetListResponse(
        items=[GoldSetResponse.model_validate(gs) for gs in page.gold_sets],
        next_cursor=next_cursor,
    )


@gold_set_router.get(
    "/{gold_set_id}",
    response_model=GoldSetWithRevisionResponse,
    operation_id="getGoldSet",
)
async def get_gold_set_route(
    gold_set_id: UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[GoldSetReader, Depends(get_gold_set_reader)],
) -> GoldSetWithRevisionResponse:
    snapshot = await get_gold_set(
        tenant_context=tenant_context,
        gold_set_id=gold_set_id,
        reader=reader,
    )
    if snapshot is None:
        # The application layer's GoldSetNotFoundError handles 404 with no
        # information leakage; cross-tenant access is structurally
        # indistinguishable from genuine not-found at the per-tenant
        # adapter layer per the audit precedent (D103).
        from contexts.retrieval_evaluation.application.append_entry_to_revision import (
            GoldSetNotFoundError,
        )
        raise GoldSetNotFoundError(
            f"gold set {gold_set_id} not found for tenant"
        )
    return GoldSetWithRevisionResponse(
        gold_set=GoldSetResponse.model_validate(snapshot.gold_set),
        current_revision=(
            GoldSetRevisionResponse.model_validate(snapshot.current_revision)
            if snapshot.current_revision is not None
            else None
        ),
        entries=[
            GoldSetEntryResponse.model_validate(e) for e in snapshot.entries
        ],
    )


@gold_set_router.post(
    "/{gold_set_id}/entries",
    response_model=AppendEntryResponse,
    operation_id="appendGoldSetEntry",
    status_code=201,
)
async def append_gold_set_entry_route(
    gold_set_id: UUID,
    body: AppendEntryRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    principal: Annotated[Principal, Depends(get_principal)],
    reader: Annotated[GoldSetReader, Depends(get_gold_set_reader)],
    repository: Annotated[GoldSetRepository, Depends(get_gold_set_repository)],
) -> AppendEntryResponse:
    result = await append_entry_to_revision(
        tenant_context=tenant_context,
        gold_set_id=gold_set_id,
        query=body.query,
        expected_chunk_ids=tuple(body.expected_chunk_ids),
        created_by_user_id=principal.subject,
        reader=reader,
        repository=repository,
    )
    return AppendEntryResponse(
        revision=GoldSetRevisionResponse.model_validate(result.revision),
        entry=GoldSetEntryResponse.model_validate(result.entry),
        opened_new_draft=result.opened_new_draft,
    )


@gold_set_router.post(
    "/{gold_set_id}/finalize",
    response_model=FinalizeRevisionResponse,
    operation_id="finalizeGoldSetRevision",
)
async def finalize_gold_set_route(
    gold_set_id: UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[GoldSetReader, Depends(get_gold_set_reader)],
    repository: Annotated[GoldSetRepository, Depends(get_gold_set_repository)],
) -> FinalizeRevisionResponse:
    result = await finalize_revision(
        tenant_context=tenant_context,
        gold_set_id=gold_set_id,
        reader=reader,
        repository=repository,
    )
    return FinalizeRevisionResponse(
        revision=GoldSetRevisionResponse.model_validate(result.revision),
        this_event_hash=result.this_event_hash,
        previous_event_hash=result.previous_event_hash,
    )


# ---------------------------------------------------------------------------
# Discovery (Stage 1 of the two-step gold-set authoring decomposition)
# ---------------------------------------------------------------------------


@discovery_router.get(
    "",
    response_model=RetrievalCandidatesResponse,
    operation_id="listRetrievalCandidates",
)
async def list_retrieval_candidates_route(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    retrieval_client: Annotated[object, Depends(get_retrieval_client)],
    query: Annotated[str, Query(min_length=1, description="Discovery query.")],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> RetrievalCandidatesResponse:
    """Stage 1: surface ranked candidates the operator selects from.

    Stage 2 is ``POST /gold-sets/{id}/entries`` where the operator
    posts the chosen ``expected_chunk_ids``. The two-step shape
    preserves human-in-the-loop content-fit selection per D112
    commitment 1 / S40b precedent.
    """
    candidates = await retrieval_client.search_vector(
        query=query,
        scope=tenant_context,
        limit=limit,
    )
    return RetrievalCandidatesResponse(
        candidates=[
            RetrievalCandidateResponse.model_validate(c) for c in candidates
        ],
    )


# ---------------------------------------------------------------------------
# Evaluation runs
# ---------------------------------------------------------------------------


@evaluation_run_router.post(
    "",
    response_model=StartEvaluationRunResponse,
    operation_id="startEvaluationRun",
    status_code=201,
)
async def start_evaluation_run_route(
    body: StartEvaluationRunRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    principal: Annotated[Principal, Depends(get_principal)],
    gold_set_reader: Annotated[GoldSetReader, Depends(get_gold_set_reader)],
    repository: Annotated[
        EvaluationRunRepository, Depends(get_evaluation_run_repository)
    ],
    retrieval_runner: Annotated[
        RetrievalRunnerPort, Depends(get_retrieval_runner_port)
    ],
    audit_port: Annotated[AuditPort, Depends(get_audit_port)],
) -> StartEvaluationRunResponse:
    """Synchronous evaluation-run kickoff per Finding 3 / D112 commitment 4.

    Blocks until the run terminates (completed or failed). The
    underlying engine raises GoldSetNotFoundError or
    GoldSetMissingFinalizedRevisionError if the named gold-set is
    missing or has no finalized revision; the registered handlers
    translate to 404 / 400 with no information leakage.
    """
    result = await run_retrieval_evaluation(
        tenant_context=tenant_context,
        gold_set_id=body.gold_set_id,
        invoked_by_user_id=principal.subject,
        reader=gold_set_reader,
        repository=repository,
        retrieval_runner=retrieval_runner,
        audit_port=audit_port,
        metric_calculator=BinaryRelevanceMetrics(),
    )
    return StartEvaluationRunResponse(
        run=EvaluationRunResponse.model_validate(result.run),
        results=[EvaluationResultResponse.model_validate(r) for r in result.results],
        aggregates=[
            EvaluationAggregateResponse.model_validate(a)
            for a in result.aggregates
        ],
    )


@evaluation_run_router.get(
    "",
    response_model=EvaluationRunListResponse,
    operation_id="listEvaluationRuns",
)
async def list_evaluation_runs_route(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[EvaluationRunReader, Depends(get_evaluation_run_reader)],
    query: Annotated[
        tuple[str | None, int], Depends(parse_evaluation_run_list_query)
    ],
) -> EvaluationRunListResponse:
    cursor, page_size = query
    page, next_cursor = await list_evaluation_runs(
        tenant_context=tenant_context,
        reader=reader,
        encoded_cursor=cursor,
        page_size=page_size,
    )
    return EvaluationRunListResponse(
        items=[EvaluationRunResponse.model_validate(r) for r in page.runs],
        next_cursor=next_cursor,
    )


@evaluation_run_router.get(
    "/{run_id}",
    response_model=EvaluationRunSnapshotResponse,
    operation_id="getEvaluationRun",
)
async def get_evaluation_run_route(
    run_id: UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[EvaluationRunReader, Depends(get_evaluation_run_reader)],
) -> EvaluationRunSnapshotResponse:
    snapshot = await get_evaluation_run(
        tenant_context=tenant_context,
        run_id=run_id,
        reader=reader,
    )
    if snapshot is None:
        raise EvaluationRunNotFoundError(str(run_id))
    return EvaluationRunSnapshotResponse(
        run=EvaluationRunResponse.model_validate(snapshot.run),
        results=[
            EvaluationResultResponse.model_validate(r) for r in snapshot.results
        ],
        aggregates=[
            EvaluationAggregateResponse.model_validate(a)
            for a in snapshot.aggregates
        ],
    )


__all__ = [
    "discovery_router",
    "evaluation_run_router",
    "get_audit_port",
    "get_evaluation_run_reader",
    "get_evaluation_run_repository",
    "get_gold_set_reader",
    "get_gold_set_repository",
    "get_retrieval_client",
    "get_retrieval_runner_port",
    "gold_set_router",
]
