"""HTTP routes for the daily-driver context (D157, S58).

The first operator-facing daily-driver surface:

- ``GET  /api/v1/daily-driver/today`` — the prioritised-today list
  (OPEN Cases + Commitments), each with computed status and default
  priority order, the user's persisted ordering applied.
- ``POST /api/v1/daily-driver/commitments`` — create a user-authored
  Commitment.
- ``POST /api/v1/daily-driver/commitments/{id}/completions`` — log a
  completion (clears the "behind on this" signal at render).
- ``PUT  /api/v1/daily-driver/today/order`` — persist the user's
  ordering.
- ``POST /api/v1/daily-driver/today/done`` — set an item's
  done-for-today mark.

Plus the served operator surface:

- ``GET /app`` — the self-contained daily-driver HTML page (auth-exempt
  per ``_PUBLIC_PATHS``; the page carries a dev-token field and makes
  authenticated fetches to the routes above).

Each data route resolves a request-scoped ``ActorContext`` via
``get_actor_context``; the use cases enforce authorisation at the
use-case boundary, and an ``AuthorisationDenied`` propagates to the 403
handler at ``apps/api/_auth_errors.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse

from apps.api.middleware import get_actor_context
from apps.api.routers._daily_driver_dto import (
    CommitmentDTO,
    CompletionDTO,
    CreateCommitmentRequest,
    GoalReadingDTO,
    MarkDoneRequest,
    RecordObservedOutcomeRequest,
    CddDraftSummaryDTO,
    CddDraftResultDTO,
    CorrectCddElementRequest,
    GoalCddDTO,
    goal_cdd_to_dto,
    FacetSuggestionDTO,
    GoalAssessmentDTO,
    GoalGroupedUnitsDTO,
    SetOrderRequest,
    TaskDTO,
    TodayDTO,
    UnitDTO,
    _empty_assessment_dto,
    _empty_grouped_units_dto,
    facet_suggestion_to_dto,
    goal_assessment_to_dto,
    goal_reading_to_dto,
    grouped_units_to_dto,
    task_to_dto,
    today_view_to_dto,
    unit_view_to_dto,
)
from contexts.daily_driver.application import (
    create_commitment,
    list_facet_suggestions,
    list_goal_assessment,
    list_goals,
    list_today,
    list_units,
    list_units_by_goal,
    log_commitment_completion,
    mark_item_done,
    raise_goal_target,
    record_observed_outcome,
    set_today_order,
)
from contexts.daily_driver.application.draft_goal_cdd import draft_goal_cdds
from contexts.daily_driver.application.proof_goal_cdd import (
    accept_cdd_element,
    correct_cdd_element,
    read_goal_cdd,
    reject_cdd_element,
)
from contexts.daily_driver.domain.cdd import ElementKind
from contexts.daily_driver.domain.commitment import Commitment
from contexts.daily_driver.ports import (
    CalendarEventsReader,
    CommitmentRepository,
    DayRepository,
    GoalGraphPort,
    OpenCasesReader,
)
from shared_kernel import ActorContext

router = APIRouter(prefix="/api/v1/daily-driver", tags=["daily-driver"])
ui_router = APIRouter(tags=["daily-driver-ui"])

_PAGE_PATH = Path(__file__).resolve().parent.parent / "static" / "daily_driver.html"


def _state(request: Request, name: str) -> object:
    value = getattr(request.app.state, name, None)
    if value is None:
        raise HTTPException(
            status_code=503,
            detail=f"{name} not configured on this API instance",
        )
    return value


def get_commitment_repository(request: Request) -> CommitmentRepository:
    """FastAPI dependency: the daily-driver CommitmentRepository."""
    return _state(request, "daily_driver_commitment_repository")  # type: ignore[return-value]


def get_day_repository(request: Request) -> DayRepository:
    """FastAPI dependency: the daily-driver DayRepository."""
    return _state(request, "daily_driver_day_repository")  # type: ignore[return-value]


def get_open_cases_reader(request: Request) -> OpenCasesReader:
    """FastAPI dependency: the daily-driver OpenCasesReader."""
    return _state(request, "daily_driver_open_cases_reader")  # type: ignore[return-value]


def get_calendar_events_reader(request: Request) -> CalendarEventsReader | None:
    """FastAPI dependency: the daily-driver CalendarEventsReader, if wired (D159).

    Optional: returns ``None`` when unconfigured so the today list degrades
    to Cases + Commitments rather than 503ing for an instance without the
    calendar seam.
    """
    return getattr(request.app.state, "daily_driver_calendar_reader", None)


def get_goal_graph(request: Request) -> GoalGraphPort:
    """FastAPI dependency: the daily-driver GoalGraphPort (D163)."""
    return _state(request, "daily_driver_goal_graph")  # type: ignore[return-value]


def get_cdd_drafter(request: Request):
    """FastAPI dependency: the daily-driver CddDrafterPort (S102, D200)."""
    return _state(request, "daily_driver_cdd_drafter")


def get_tasks_reader(request: Request):
    """FastAPI dependency: the daily-driver Tasks reader (D167), if wired.

    Optional: returns ``None`` when unconfigured so /tasks degrades to an empty
    list rather than 503ing for an instance without the tasks seam.
    """
    return getattr(request.app.state, "daily_driver_tasks_reader", None)


def get_unit_graph(request: Request):
    """FastAPI dependency: the daily-driver UnitGraphPort (D168), if wired."""
    return getattr(request.app.state, "daily_driver_unit_graph", None)


def get_facet_source(request: Request):
    """FastAPI dependency: the daily-driver FacetSource (D168), if wired."""
    return getattr(request.app.state, "daily_driver_facet_source", None)


def get_email_job_search_source(request: Request):
    """FastAPI dependency: the EmailJobSearchSource (D183/S89), if wired."""
    return getattr(request.app.state, "daily_driver_email_job_search_source", None)


def get_goal_graph_optional(request: Request):
    """FastAPI dependency: the GoalGraphPort if wired, else None (D169).

    The assessment route degrades to empty reads when any correlation seam is
    unconfigured, so it needs the optional form (the required ``get_goal_graph``
    503s on absence for the /goals route)."""
    return getattr(request.app.state, "daily_driver_goal_graph", None)


def get_drop_candidate_quiet_days(request: Request) -> int | None:
    """FastAPI dependency: the configured drop-candidate quiet window (D162).

    Returns ``None`` when unconfigured so the today list degrades to the
    S60 view (no drop-candidate flagging) rather than guessing a threshold.
    """
    return getattr(
        request.app.state, "daily_driver_drop_candidate_quiet_days", None
    )


def _commitment_to_dto(commitment: Commitment) -> CommitmentDTO:
    return CommitmentDTO(
        id=commitment.id,
        name=commitment.name,
        expected_interval_days=commitment.expected_interval_days,
        created_at=commitment.created_at,
        expected_outcome=commitment.expected_outcome,
        observed_outcome=commitment.observed_outcome,
        outcome_status=(
            commitment.outcome_status.value
            if commitment.outcome_status is not None
            else None
        ),
        observed_at=commitment.observed_at,
    )


@router.get("/today", response_model=TodayDTO)
async def get_today(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    open_cases_reader: Annotated[
        OpenCasesReader, Depends(get_open_cases_reader)
    ],
    commitment_repository: Annotated[
        CommitmentRepository, Depends(get_commitment_repository)
    ],
    day_repository: Annotated[DayRepository, Depends(get_day_repository)],
    calendar_events_reader: Annotated[
        CalendarEventsReader | None, Depends(get_calendar_events_reader)
    ],
    goal_graph: Annotated[
        GoalGraphPort | None, Depends(get_goal_graph_optional)
    ],
    drop_candidate_quiet_days: Annotated[
        int | None, Depends(get_drop_candidate_quiet_days)
    ],
) -> TodayDTO:
    """Return the actor's prioritised-today list (Cases + Commitments + calendar)."""
    view = await list_today(
        open_cases_reader=open_cases_reader,
        commitment_repository=commitment_repository,
        day_repository=day_repository,
        actor=actor,
        calendar_events_reader=calendar_events_reader,
        goal_graph=goal_graph,
        drop_candidate_quiet_days=drop_candidate_quiet_days,
    )
    return today_view_to_dto(view)


@router.post("/commitments", response_model=CommitmentDTO, status_code=201)
async def post_commitment(
    body: CreateCommitmentRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    commitment_repository: Annotated[
        CommitmentRepository, Depends(get_commitment_repository)
    ],
) -> CommitmentDTO:
    """Create a user-authored Commitment."""
    commitment = await create_commitment(
        repository=commitment_repository,
        actor=actor,
        name=body.name,
        expected_interval_days=body.expected_interval_days,
        expected_outcome=body.expected_outcome,
    )
    return _commitment_to_dto(commitment)


@router.post(
    "/commitments/{commitment_id}/completions",
    response_model=CompletionDTO,
    status_code=201,
)
async def post_completion(
    commitment_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    commitment_repository: Annotated[
        CommitmentRepository, Depends(get_commitment_repository)
    ],
) -> CompletionDTO:
    """Log a completion for a Commitment (clears the overdue signal)."""
    completion = await log_commitment_completion(
        repository=commitment_repository,
        actor=actor,
        commitment_id=commitment_id,
    )
    if completion is None:
        raise HTTPException(status_code=404, detail="commitment not found")
    return CompletionDTO(
        id=completion.id,
        commitment_id=completion.commitment_id,
        completed_at=completion.completed_at,
    )


@router.post(
    "/commitments/{commitment_id}/observed-outcome",
    response_model=CommitmentDTO,
)
async def post_observed_outcome(
    commitment_id: UUID,
    body: RecordObservedOutcomeRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    commitment_repository: Annotated[
        CommitmentRepository, Depends(get_commitment_repository)
    ],
) -> CommitmentDTO:
    """Record what transpired for a Commitment (D162) — the back half of the loop."""
    commitment = await record_observed_outcome(
        repository=commitment_repository,
        actor=actor,
        commitment_id=commitment_id,
        observed_outcome=body.observed_outcome,
        outcome_status=body.outcome_status,
    )
    if commitment is None:
        raise HTTPException(status_code=404, detail="commitment not found")
    return _commitment_to_dto(commitment)


@router.get("/goals", response_model=list[GoalReadingDTO])
async def get_goals(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
    commitment_repository: Annotated[
        CommitmentRepository, Depends(get_commitment_repository)
    ],
) -> list[GoalReadingDTO]:
    """Read each goal against its lever — target, progress, gap, recommendation (D163)."""
    readings = await list_goals(
        goal_graph=goal_graph,
        commitment_repository=commitment_repository,
        actor=actor,
    )
    return [goal_reading_to_dto(r) for r in readings]


@router.post("/goals/{outcome_id}/raise-target", response_model=GoalReadingDTO)
async def post_raise_target(
    outcome_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
    commitment_repository: Annotated[
        CommitmentRepository, Depends(get_commitment_repository)
    ],
) -> GoalReadingDTO:
    """Raise the goal's target one level (D163) — explicit, never automatic (D9).

    Returns the re-read goal on success; 409 when the goal is absent or already
    at the top of the ladder (nothing to raise to).
    """
    new_level = await raise_goal_target(
        goal_graph=goal_graph, actor=actor, outcome_id=outcome_id
    )
    if new_level is None:
        raise HTTPException(
            status_code=409,
            detail="cannot raise: goal not found or already at the top of the ladder",
        )
    readings = await list_goals(
        goal_graph=goal_graph,
        commitment_repository=commitment_repository,
        actor=actor,
    )
    reading = next((r for r in readings if r.goal.id == outcome_id), None)
    if reading is None:
        raise HTTPException(status_code=404, detail="goal not found after raise")
    return goal_reading_to_dto(reading)


# --- The authored CDD layer (S102, D200) -----------------------------------


@router.post("/cdd/draft", response_model=CddDraftSummaryDTO)
async def post_draft_cdd(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
    drafter: Annotated[object, Depends(get_cdd_drafter)],
    commitment_repository: Annotated[
        CommitmentRepository, Depends(get_commitment_repository)
    ],
) -> CddDraftSummaryDTO:
    """Draft each goal's CDD via the structured-output port (S102, D200).

    Safely re-runnable: a goal that already carries authored elements is skipped.
    The matcher's SERVES/LEVER_FOR layer is untouched.
    """
    results = await draft_goal_cdds(
        goal_graph=goal_graph,
        drafter=drafter,
        actor=actor,
        commitment_repository=commitment_repository,
    )
    return CddDraftSummaryDTO(
        results=[
            CddDraftResultDTO(
                outcome_id=r.outcome_id,
                name=r.name,
                drafted=r.drafted,
                skipped_existing=r.skipped_existing,
                levers=r.levers,
                intermediaries=r.intermediaries,
                externals=r.externals,
            )
            for r in results
        ]
    )


@router.get("/cdd/{outcome_id}", response_model=GoalCddDTO)
async def get_goal_cdd(
    outcome_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> GoalCddDTO:
    """Read a goal's drafted CDD for proof review (S102, D200)."""
    view = await read_goal_cdd(
        goal_graph=goal_graph, actor=actor, outcome_id=outcome_id
    )
    return goal_cdd_to_dto(view)


@router.post("/cdd/elements/{kind}/{element_id}/accept", status_code=204)
async def post_accept_cdd_element(
    kind: ElementKind,
    element_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Accept an authored element (proof_state -> accepted, S102)."""
    ok = await accept_cdd_element(
        goal_graph=goal_graph, actor=actor, kind=kind, element_id=element_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="authored element not found")
    return Response(status_code=204)


@router.post("/cdd/elements/{kind}/{element_id}/correct", status_code=204)
async def post_correct_cdd_element(
    kind: ElementKind,
    element_id: UUID,
    body: CorrectCddElementRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Edit an element's label and flip its origin to user_authored (S102, D200)."""
    ok = await correct_cdd_element(
        goal_graph=goal_graph, actor=actor, kind=kind, element_id=element_id,
        label=body.label,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="authored element not found")
    return Response(status_code=204)


@router.post("/cdd/elements/{kind}/{element_id}/reject", status_code=204)
async def post_reject_cdd_element(
    kind: ElementKind,
    element_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Remove an authored element — the user-initiated delete (S102)."""
    ok = await reject_cdd_element(
        goal_graph=goal_graph, actor=actor, kind=kind, element_id=element_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="authored element not found")
    return Response(status_code=204)


@router.get("/tasks", response_model=list[TaskDTO])
async def get_tasks(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    tasks_reader: Annotated[object | None, Depends(get_tasks_reader)],
) -> list[TaskDTO]:
    """Return the actor's ingested Google tasks as their own view (D167).

    Not correlated to calendar or goals — correlation into units of work is P18.
    Degrades to an empty list when the tasks seam is unconfigured.
    """
    if tasks_reader is None:
        return []
    tasks = await tasks_reader.list_tasks(actor=actor)
    return [task_to_dto(t) for t in tasks]


@router.get("/units", response_model=list[UnitDTO])
async def get_units(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    unit_graph: Annotated[object | None, Depends(get_unit_graph)],
    facet_source: Annotated[object | None, Depends(get_facet_source)],
) -> list[UnitDTO]:
    """Return the actor's correlated units of work (D168, D166).

    Each unit is shown *as a unit* — its facets (task, calendar block,
    email-origin) grouped — with below-floor matches flagged as candidates.
    Degrades to an empty list when the correlation seams are unconfigured (no
    graph reachable); the units are populated by the operator-gated correlate
    run, not on read.
    """
    if unit_graph is None or facet_source is None:
        return []
    units = await list_units(
        unit_graph=unit_graph, facet_source=facet_source, actor=actor
    )
    return [unit_view_to_dto(u) for u in units]


@router.get("/assessment", response_model=GoalAssessmentDTO)
async def get_assessment(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    unit_graph: Annotated[object | None, Depends(get_unit_graph)],
    facet_source: Annotated[object | None, Depends(get_facet_source)],
    goal_graph: Annotated[object | None, Depends(get_goal_graph_optional)],
) -> GoalAssessmentDTO:
    """Return the two moat reads — orphan work + the neglected goal (D169, D166).

    Recommendation-shaped, never auto-acting. Degrades to empty reads when the
    correlation seams are unconfigured. The goal facets are populated by the
    operator-gated correlate run, not on read.
    """
    if unit_graph is None or facet_source is None or goal_graph is None:
        return _empty_assessment_dto()
    assessment = await list_goal_assessment(
        unit_graph=unit_graph,
        facet_source=facet_source,
        goal_graph=goal_graph,
        actor=actor,
    )
    return goal_assessment_to_dto(assessment)


@router.get("/units-by-goal", response_model=GoalGroupedUnitsDTO)
async def get_units_by_goal(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    unit_graph: Annotated[object | None, Depends(get_unit_graph)],
    facet_source: Annotated[object | None, Depends(get_facet_source)],
    goal_graph: Annotated[object | None, Depends(get_goal_graph_optional)],
    email_job_search_source: Annotated[
        object | None, Depends(get_email_job_search_source)
    ],
    commitment_repository: Annotated[
        CommitmentRepository, Depends(get_commitment_repository)
    ],
) -> GoalGroupedUnitsDTO:
    """Return the moat view anchored on the goal served (D180).

    Units grouped under the ``:Outcome`` each ``SERVES``; orphan units under one
    unlinked group (coverage-gated, D171); the D175 fold applied before
    grouping. Job-search email activity folds to a count by kind and reads
    active on recency (D183/S89). Each goal carries its status (D187/S92) —
    on-track / behind / stalled / done / active. A read-and-render projection —
    no graph write. Degrades to an empty view when the seams are unconfigured.
    """
    if unit_graph is None or facet_source is None or goal_graph is None:
        return _empty_grouped_units_dto()
    grouped = await list_units_by_goal(
        unit_graph=unit_graph,
        facet_source=facet_source,
        goal_graph=goal_graph,
        actor=actor,
        email_job_search_source=email_job_search_source,
        commitment_repository=commitment_repository,
    )
    return grouped_units_to_dto(grouped)


@router.get("/suggestions", response_model=list[FacetSuggestionDTO])
async def get_suggestions(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    unit_graph: Annotated[object | None, Depends(get_unit_graph)],
    facet_source: Annotated[object | None, Depends(get_facet_source)],
    goal_graph: Annotated[object | None, Depends(get_goal_graph_optional)],
) -> list[FacetSuggestionDTO]:
    """Return the missing-facet suggestions (D170, D166, D196).

    Selective and confident or silent — credulity-gated on goal-serving units,
    relevance-gated so a homeostatic maintenance rhythm gets no planning nudge
    (D196), never auto-applied, never written back. Degrades to an empty list
    when the correlation seams are unconfigured.
    """
    if unit_graph is None or facet_source is None or goal_graph is None:
        return []
    suggestions = await list_facet_suggestions(
        unit_graph=unit_graph,
        facet_source=facet_source,
        goal_graph=goal_graph,
        actor=actor,
    )
    return [facet_suggestion_to_dto(s) for s in suggestions]


@router.put("/today/order", status_code=204)
async def put_order(
    body: SetOrderRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    day_repository: Annotated[DayRepository, Depends(get_day_repository)],
) -> Response:
    """Persist the user's ordering of today-items."""
    await set_today_order(
        day_repository=day_repository,
        actor=actor,
        ordered_keys=tuple((ref.kind, ref.item_id) for ref in body.ordered),
        now=datetime.now(timezone.utc),
    )
    return Response(status_code=204)


@router.post("/today/done", status_code=204)
async def post_done(
    body: MarkDoneRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    day_repository: Annotated[DayRepository, Depends(get_day_repository)],
) -> Response:
    """Set or clear an item's done-for-today mark."""
    await mark_item_done(
        day_repository=day_repository,
        actor=actor,
        kind=body.kind,
        item_id=body.item_id,
        done=body.done,
        now=datetime.now(timezone.utc),
    )
    return Response(status_code=204)


@ui_router.get("/app", include_in_schema=False)
async def daily_driver_page() -> FileResponse:
    """Serve the self-contained daily-driver operator surface (auth-exempt)."""
    return FileResponse(_PAGE_PATH, media_type="text/html")


__all__ = ["router", "ui_router"]
