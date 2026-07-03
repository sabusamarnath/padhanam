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
    AddCddElementRequest,
    AddedCddElementDTO,
    CLOSE_REASONS,
    CloseOpportunityRequest,
    RestageOpportunityRequest,
    CreateLeadRequest,
    CreateLeadResponse,
    AddContactRequest,
    AddContactResponse,
    ContactDTO,
    EnrichContactRequest,
    SetContactRoleRequest,
    contact_to_dto,
    LogWarmingStepRequest,
    WarmingStepDTO,
    warming_step_to_dto,
    QualificationFieldDTO,
    SetQualificationRequest,
    ExtractJdRequest,
    qualification_to_dto,
    LogActivityRequest,
    ActivityEntryDTO,
    activity_to_dto,
    ElementBindingDTO,
    ElementEvidenceSummaryDTO,
    EmailSourceDTO,
    PipelineAssessmentDTO,
    PipelineStatsDTO,
    pipeline_assessment_to_dto,
    pipeline_stats_to_dto,
    ReclassifyCddElementRequest,
    RelinkCddEvidenceRequest,
    RematchResultDTO,
    UnlinkCddEvidenceRequest,
    element_binding_to_dto,
    element_evidence_summary_to_dto,
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
    ActWorklistDTO,
    act_worklist_to_dto,
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
from contexts.daily_driver.application.create_lead import (
    LeadValidationError,
    create_lead,
)
from contexts.daily_driver.application.manage_contacts import (
    ContactValidationError,
    add_contact,
    confirm_contact as confirm_contact_uc,
    enrich_contact as enrich_contact_uc,
    list_contacts as list_contacts_uc,
    reject_contact as reject_contact_uc,
    set_contact_role as set_contact_role_uc,
)
from contexts.daily_driver.application.warming_steps import (
    WarmingStepError,
    list_warming_steps as list_warming_steps_uc,
    log_warming_step as log_warming_step_uc,
)
from contexts.daily_driver.application.qualification import (
    QualificationError,
    dismiss_qualification_draft as dismiss_qualification_draft_uc,
    read_opportunity_qualification as read_qualification_uc,
    set_qualification_field as set_qualification_field_uc,
)
from contexts.daily_driver.application.extract_jd import (
    extract_jd_qualification as extract_jd_uc,
)
from contexts.daily_driver.application.activity import (
    ActivityError,
    list_opportunity_activity as list_activity_uc,
    log_opportunity_activity as log_activity_uc,
)
from contexts.daily_driver.application.author_cdd import (
    add_cdd_element,
    reclassify_cdd_element,
)
from contexts.daily_driver.application.correlate_goal_facets import (
    correlate_goal_facets,
)
from contexts.daily_driver.application.read_element_evidence import (
    read_element_bindings,
    read_element_evidence,
)
from contexts.daily_driver.application.read_pipeline_assessment import (
    read_pipeline_assessment,
)
from contexts.daily_driver.application.read_pipeline_stats import (
    read_pipeline_stats,
)
from contexts.daily_driver.application.read_act_worklist import (
    read_act_worklist,
)
from contexts.daily_driver.application.correct_cdd_evidence import (
    relink_cdd_evidence,
    unlink_cdd_evidence,
)
from contexts.daily_driver.application.draft_goal_cdd import draft_goal_cdds
from contexts.daily_driver.application.proof_goal_cdd import (
    accept_cdd_element,
    accept_cdd_outcome,
    correct_cdd_element,
    correct_cdd_outcome,
    read_goal_cdd,
    reject_cdd_element,
    reject_cdd_outcome,
)
from contexts.daily_driver.domain.cdd import EVIDENCE_KINDS, ElementKind
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


def get_cdd_audit_port(request: Request):
    """FastAPI dependency: the audit port for CDD-correction capture (D203,
    S103c), if wired. None degrades to mutate-without-capture."""
    return getattr(request.app.state, "daily_driver_audit_port", None)


def get_audit_reader(request: Request):
    """FastAPI dependency: the faceted audit reader (D102), for reading warming
    steps back per subject (S103v, D224). None when unwired."""
    return getattr(request.app.state, "audit_event_reader", None)


def get_cdd_drafter(request: Request):
    """FastAPI dependency: the daily-driver CddDrafterPort (S102, D200)."""
    return _state(request, "daily_driver_cdd_drafter")


def get_jd_extractor(request: Request):
    """FastAPI dependency: the daily-driver JdExtractorPort (S103ad, D236)."""
    return _state(request, "daily_driver_jd_extractor")


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


def get_email_source_metadata(request: Request):
    """FastAPI dependency: the EmailSourceMetadataSource (D209), if wired."""
    return getattr(request.app.state, "daily_driver_email_source_metadata", None)


def get_email_content_source(request: Request):
    """FastAPI dependency: the EmailContentSource (D212) for the drawer's openable
    read-only source, if wired."""
    return getattr(request.app.state, "daily_driver_email_content_source", None)


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


@router.get("/act", response_model=ActWorklistDTO)
async def get_act_worklist(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    commitment_repository: Annotated[
        CommitmentRepository, Depends(get_commitment_repository)
    ],
    open_cases_reader: Annotated[
        OpenCasesReader, Depends(get_open_cases_reader)
    ],
    goal_graph: Annotated[
        GoalGraphPort | None, Depends(get_goal_graph_optional)
    ],
    unit_graph: Annotated[object | None, Depends(get_unit_graph)],
    facet_source: Annotated[object | None, Depends(get_facet_source)],
    audit_reader: Annotated[object | None, Depends(get_audit_reader)],
    calendar_events_reader: Annotated[
        CalendarEventsReader | None, Depends(get_calendar_events_reader)
    ],
) -> ActWorklistDTO:
    """The act worklist (D232): the six-source union — pipeline next-best-actions,
    warming steps due, stale qualification, commitments, calendar, and open cases —
    over one day, tagged and sorted by urgency. The surface cuts it into Today /
    Week / doing. A projection; each source degrades cleanly if its seam is
    absent."""
    now = datetime.now(timezone.utc)
    items = await read_act_worklist(
        goal_graph=goal_graph, commitment_repository=commitment_repository,
        open_cases_reader=open_cases_reader, actor=actor,
        unit_graph=unit_graph, facet_source=facet_source,
        audit_reader=audit_reader,
        calendar_events_reader=calendar_events_reader, now=now,
    )
    return act_worklist_to_dto(items, day_date=now.date())


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


@router.post(
    "/cdd/{outcome_id}/elements",
    response_model=AddedCddElementDTO,
    status_code=201,
)
async def post_add_cdd_element(
    outcome_id: UUID,
    body: AddCddElementRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> AddedCddElementDTO:
    """Add a user-authored element of any of the four types (S103a).

    The outcome routes to the authored outcome stance (the goal's single
    terminal); a lever / intermediary / external creates a new element node with
    a default edge to the outcome. The path by which externals enter the model.
    """
    if body.kind == "outcome":
        await correct_cdd_outcome(
            goal_graph=goal_graph, actor=actor, outcome_id=outcome_id,
            label=body.label,
        )
        return AddedCddElementDTO(element_id=None)
    try:
        kind = ElementKind(body.kind)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"unknown element kind: {body.kind}"
        )
    element_id = await add_cdd_element(
        goal_graph=goal_graph, actor=actor, outcome_id=outcome_id,
        kind=kind, label=body.label,
    )
    return AddedCddElementDTO(element_id=element_id)


@router.get("/cdd/evidence", response_model=ElementEvidenceSummaryDTO)
async def get_cdd_evidence(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    unit_graph: Annotated[object | None, Depends(get_unit_graph)],
) -> ElementEvidenceSummaryDTO:
    """Read-only element-evidence summary (D202, S103b): per-element unit counts +
    the unbound bucket. Degrades to zeros when the unit graph is unwired. Declared
    before ``/cdd/{outcome_id}`` so ``evidence`` is not parsed as an outcome id."""
    if unit_graph is None:
        return ElementEvidenceSummaryDTO()
    summary = await read_element_evidence(unit_graph=unit_graph, actor=actor)
    return element_evidence_summary_to_dto(summary)


@router.get("/cdd/bindings", response_model=list[ElementBindingDTO])
async def get_cdd_bindings(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    unit_graph: Annotated[object | None, Depends(get_unit_graph)],
    facet_source: Annotated[object | None, Depends(get_facet_source)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> list[ElementBindingDTO]:
    """Each unit→element binding with its title, user-ownership, and a recomputed
    why + match-strength (D203/S103c-fix), for the interactive lens. Declared
    before ``/cdd/{outcome_id}`` so ``bindings`` is not parsed as an outcome id."""
    if unit_graph is None or facet_source is None:
        return []
    bindings = await read_element_bindings(
        unit_graph=unit_graph, facet_source=facet_source,
        goal_graph=goal_graph, actor=actor,
    )
    return [element_binding_to_dto(b) for b in bindings]


@router.get("/cdd/pipeline-stats/{outcome_id}", response_model=PipelineStatsDTO)
async def get_cdd_pipeline_stats(
    outcome_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
    unit_graph: Annotated[object | None, Depends(get_unit_graph)],
    facet_source: Annotated[object | None, Depends(get_facet_source)],
    audit_reader: Annotated[object | None, Depends(get_audit_reader)],
) -> PipelineStatsDTO:
    """The Pipeline stats for a goal (D217): the three-way split, the depth ladder,
    and the engaged Kanban (gate columns + cards with next-best-action). Declared
    before ``/cdd/{outcome_id}``."""
    if unit_graph is None or facet_source is None:
        raise HTTPException(status_code=503, detail="pipeline-stats seams not configured")
    stats = await read_pipeline_stats(
        goal_graph=goal_graph, unit_graph=unit_graph, facet_source=facet_source,
        outcome_id=outcome_id, actor=actor, audit_reader=audit_reader,
    )
    cdd = await goal_graph.read_goal_cdd(
        tenant_context=actor.tenant_context, outcome_id=outcome_id
    )
    return pipeline_stats_to_dto(stats, gates=cdd.gates)


@router.get("/cdd/assessment/{outcome_id}", response_model=PipelineAssessmentDTO)
async def get_cdd_assessment(
    outcome_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> PipelineAssessmentDTO:
    """The "how am I doing" assessment for a goal (D216): a recommendation-shaped
    verdict whose headline is label-independent, the funnel counts, and the
    proof-dependent close-reason split. Declared before ``/cdd/{outcome_id}`` so
    ``assessment`` is not parsed as an outcome id."""
    assessment = await read_pipeline_assessment(
        goal_graph=goal_graph, outcome_id=outcome_id, actor=actor
    )
    return pipeline_assessment_to_dto(assessment)


@router.get("/cdd/email-source/{facet_id}", response_model=EmailSourceDTO)
async def get_cdd_email_source(
    facet_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    email_content_source: Annotated[
        object | None, Depends(get_email_content_source)
    ],
) -> EmailSourceDTO:
    """The read-only ingested source (sender, date, subject, body) of one email
    facet, for the verification drawer's openable-source leg (D212). Read-only — it
    shows ingested content, never fetches or writes (§9). 404 when not an email or
    absent."""
    if email_content_source is None:
        raise HTTPException(status_code=503, detail="email source not configured")
    content = await email_content_source.get_email_content(
        actor=actor, facet_id=facet_id
    )
    if content is None:
        raise HTTPException(status_code=404, detail="no email source for this item")
    return EmailSourceDTO(
        facet_id=content.facet_id,
        sender=content.sender,
        received_at=content.received_at,
        subject=content.subject,
        body=content.body,
    )


@router.post("/cdd/opportunity/{opportunity_id}/close", status_code=204)
async def post_opportunity_close(
    opportunity_id: UUID,
    body: CloseOpportunityRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Close an opportunity with a required outcome reason (D214). Archive-not-erase
    — the binds + correspondence stay, reopenable. 422 on an unknown reason, 404
    when the opportunity is absent."""
    reason = (body.reason or "").strip()
    if reason not in CLOSE_REASONS:
        raise HTTPException(
            status_code=422,
            detail=f"reason must be one of {sorted(CLOSE_REASONS)}",
        )
    ok = await goal_graph.close_opportunity(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
        closed_reason=reason,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return Response(status_code=204)


@router.post("/cdd/opportunity/{opportunity_id}/reopen", status_code=204)
async def post_opportunity_reopen(
    opportunity_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Reopen a closed opportunity back to live, whole (D214)."""
    ok = await goal_graph.reopen_opportunity(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return Response(status_code=204)


@router.post("/cdd/opportunity/{opportunity_id}/confirm", status_code=204)
async def post_opportunity_confirm(
    opportunity_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Confirm a system-suggested opportunity → user_authored (D215/D200): the
    operator vouches the extracted cluster is real. 404 when absent."""
    ok = await goal_graph.confirm_opportunity(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return Response(status_code=204)


@router.post("/cdd/opportunity/{opportunity_id}/stage", status_code=204)
async def post_opportunity_restage(
    opportunity_id: UUID,
    body: RestageOpportunityRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Re-stage an opportunity to a gate (D217) — the operator proofing its gate
    position; ``gate_id`` null clears it to Unplaced. The Doing assessment + the
    depth ladder read ``current_gate_id``, so the correction propagates. 404 absent."""
    ok = await goal_graph.set_opportunity_gate(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
        current_gate_id=body.gate_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return Response(status_code=204)


@router.post("/cdd/opportunity/{opportunity_id}/reject", status_code=204)
async def post_opportunity_reject(
    opportunity_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Reject (delete) a suggested opportunity (D215): the operator rejects the
    extracted cluster. The units + their binds survive (only the node + BELONGS_TO
    go), so the units return to the unclustered set. 404 when absent."""
    ok = await goal_graph.delete_opportunity(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return Response(status_code=204)


@router.post("/cdd/lead", status_code=201)
async def post_create_lead(
    body: CreateLeadRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> CreateLeadResponse:
    """Create a new lead at the goal's Lead gate (D221): a user_authored
    opportunity with zero touches and no thread, carrying the operator-set fit
    tier, warm access, and origination source. The apply-advance (Lead -> Apply)
    reuses the /stage endpoint. 422 on a bad field or a missing Lead gate."""
    try:
        opportunity_id = await create_lead(
            goal_graph=goal_graph, actor=actor, outcome_id=body.outcome_id,
            company=body.company, role=body.role, fit_tier=body.fit_tier,
            warm_access_available=body.warm_access_available,
            origination_source=body.origination_source,
        )
    except LeadValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return CreateLeadResponse(opportunity_id=opportunity_id)


# --- Contacts (S103u, D222) — the network behind warm access ----------------

@router.get("/cdd/contacts", response_model=list[ContactDTO])
async def get_contacts(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> list[ContactDTO]:
    """The tenant's contacts (D222) for the proof surface + a lead's inline list."""
    contacts = await list_contacts_uc(goal_graph=goal_graph, actor=actor)
    return [contact_to_dto(c) for c in contacts]


@router.post("/cdd/contacts", status_code=201)
async def post_add_contact(
    body: AddContactRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> AddContactResponse:
    """Add a contact email did not surface (D222) — the manual capture route
    (hand-added or LinkedIn-known). 422 on a bad vocabulary or an empty name."""
    try:
        contact_id = await add_contact(
            goal_graph=goal_graph, actor=actor, name=body.name, company=body.company,
            degree=body.degree, strength=body.strength,
            reachability=body.reachability, capture_source=body.capture_source,
        )
    except ContactValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return AddContactResponse(contact_id=contact_id)


@router.post("/cdd/contacts/{contact_id}/confirm", status_code=204)
async def post_confirm_contact(
    contact_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Confirm a system-suggested contact → user_authored (D222). 404 when absent."""
    ok = await confirm_contact_uc(
        goal_graph=goal_graph, actor=actor, contact_id=contact_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="contact not found")
    return Response(status_code=204)


@router.post("/cdd/contacts/{contact_id}/enrich", status_code=204)
async def post_enrich_contact(
    contact_id: UUID,
    body: EnrichContactRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Enrich a contact with degree/strength/reachability (D222) — flips it to
    user_authored. 422 on a bad vocabulary, 404 when absent."""
    try:
        ok = await enrich_contact_uc(
            goal_graph=goal_graph, actor=actor, contact_id=contact_id,
            degree=body.degree, strength=body.strength,
            reachability=body.reachability,
        )
    except ContactValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if not ok:
        raise HTTPException(status_code=404, detail="contact not found")
    return Response(status_code=204)


@router.post("/cdd/contacts/{contact_id}/reject", status_code=204)
async def post_reject_contact(
    contact_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Reject (delete) a contact (D222). 404 when absent."""
    ok = await reject_contact_uc(
        goal_graph=goal_graph, actor=actor, contact_id=contact_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="contact not found")
    return Response(status_code=204)


@router.post("/cdd/contacts/{contact_id}/role", status_code=204)
async def post_set_contact_role(
    contact_id: UUID,
    body: SetContactRoleRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Set a contact's hiring-process role (D227). 422 on a bad role, 404 absent."""
    try:
        ok = await set_contact_role_uc(
            goal_graph=goal_graph, actor=actor, contact_id=contact_id,
            process_role=body.process_role,
        )
    except ContactValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if not ok:
        raise HTTPException(status_code=404, detail="contact not found")
    return Response(status_code=204)


# --- Qualification (S103w, D228) — stage-aware, per opportunity ---------------

@router.get(
    "/cdd/qualification/{outcome_id}/{opportunity_id}",
    response_model=list[QualificationFieldDTO],
)
async def get_qualification(
    outcome_id: UUID,
    opportunity_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> list[QualificationFieldDTO]:
    """The eight qualification fields for an opportunity (D228) with stage-relative
    freshness (D229) — values, activation, and risk badges."""
    fields = await read_qualification_uc(
        goal_graph=goal_graph, actor=actor, outcome_id=outcome_id,
        opportunity_id=opportunity_id,
    )
    return [qualification_to_dto(f) for f in fields]


@router.post("/cdd/opportunity/{opportunity_id}/qualification", status_code=204)
async def post_set_qualification(
    opportunity_id: UUID,
    body: SetQualificationRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Author a qualification field's value (D228). 422 on an unknown field, 404
    when the opportunity is absent."""
    try:
        ok = await set_qualification_field_uc(
            goal_graph=goal_graph, actor=actor, opportunity_id=opportunity_id,
            field_key=body.field_key, value=body.value,
        )
    except QualificationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if not ok:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return Response(status_code=204)


@router.post("/cdd/opportunity/{opportunity_id}/extract-jd", status_code=204)
async def post_extract_jd(
    opportunity_id: UUID,
    body: ExtractJdRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
    jd_extractor: Annotated[object, Depends(get_jd_extractor)],
) -> Response:
    """Paste a job description onto the opportunity and draft the three JD-derivable
    qualification fields as suggestions (S103ad/D236). The drafts land in `q_<key>_draft`
    slots — never a field value; the surface then offers Use/Dismiss. Stores the JD as
    a durable source. The surface reloads the qualification to show the suggestions."""
    await extract_jd_uc(
        goal_graph=goal_graph, jd_extractor=jd_extractor, actor=actor,
        opportunity_id=opportunity_id, jd_text=body.text,
    )
    return Response(status_code=204)


@router.post(
    "/cdd/opportunity/{opportunity_id}/qualification/{field_key}/dismiss-draft",
    status_code=204,
)
async def post_dismiss_qualification_draft(
    opportunity_id: UUID,
    field_key: str,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Dismiss a JD-extracted draft suggestion (S103ad/D236) — clears the draft slot
    without writing a value. 422 on an unknown field."""
    try:
        await dismiss_qualification_draft_uc(
            goal_graph=goal_graph, actor=actor, opportunity_id=opportunity_id,
            field_key=field_key,
        )
    except QualificationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return Response(status_code=204)


# --- Opportunity activity history (S103w, D229) — append-only -----------------

@router.post("/cdd/opportunity/{opportunity_id}/activity", status_code=204)
async def post_log_activity(
    opportunity_id: UUID,
    body: LogActivityRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
    audit_port: Annotated[object | None, Depends(get_cdd_audit_port)],
) -> Response:
    """Log an activity against an opportunity (D229); a named field bumps its
    freshness. 422 on a bad field, 503 when the audit trail is unwired."""
    try:
        await log_activity_uc(
            goal_graph=goal_graph, actor=actor, opportunity_id=opportunity_id,
            kind=body.kind, note=body.note, touches_field=body.touches_field,
            audit_port=audit_port,
        )
    except ActivityError as e:
        code = 503 if "audit port" in str(e) else 422
        raise HTTPException(status_code=code, detail=str(e)) from e
    return Response(status_code=204)


@router.get(
    "/cdd/opportunity/{opportunity_id}/activity",
    response_model=list[ActivityEntryDTO],
)
async def get_activity(
    opportunity_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    audit_reader: Annotated[object | None, Depends(get_audit_reader)],
) -> list[ActivityEntryDTO]:
    """The opportunity's activity history, newest first (D229)."""
    entries = await list_activity_uc(
        actor=actor, opportunity_id=opportunity_id, audit_reader=audit_reader,
    )
    return [activity_to_dto(a) for a in entries]


# --- Warming steps (S103v, D224) — append-only, per subject -------------------

@router.post("/cdd/warming", status_code=204)
async def post_log_warming_step(
    body: LogWarmingStepRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    audit_port: Annotated[object | None, Depends(get_cdd_audit_port)],
) -> Response:
    """Log a warming step against a contact or a lead (D224) — an append-only audit
    event. 422 on a bad vocabulary, 503 when the audit trail is unwired."""
    try:
        await log_warming_step_uc(
            actor=actor, subject_type=body.subject_type, subject_id=body.subject_id,
            kind=body.kind, note=body.note, audit_port=audit_port,
        )
    except WarmingStepError as e:
        code = 503 if "audit port" in str(e) else 422
        raise HTTPException(status_code=code, detail=str(e)) from e
    return Response(status_code=204)


@router.get(
    "/cdd/warming/{subject_type}/{subject_id}", response_model=list[WarmingStepDTO]
)
async def get_warming_steps(
    subject_type: str,
    subject_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    audit_reader: Annotated[object | None, Depends(get_audit_reader)],
) -> list[WarmingStepDTO]:
    """The warming steps logged against a subject, newest first (D224)."""
    steps = await list_warming_steps_uc(
        actor=actor, subject_type=subject_type, subject_id=subject_id,
        audit_reader=audit_reader,
    )
    return [warming_step_to_dto(s) for s in steps]


@router.post("/cdd/rematch", response_model=RematchResultDTO)
async def post_cdd_rematch(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    unit_graph: Annotated[object | None, Depends(get_unit_graph)],
    facet_source: Annotated[object | None, Depends(get_facet_source)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
    commitment_repository: Annotated[
        CommitmentRepository, Depends(get_commitment_repository)
    ],
    email_job_search_source: Annotated[
        object | None, Depends(get_email_job_search_source)
    ],
    email_source_metadata: Annotated[
        object | None, Depends(get_email_source_metadata)
    ],
) -> RematchResultDTO:
    """Re-run the element matcher over existing units against the current element
    set (D202/D203, S103c). Idempotent and correction-respecting: it skips
    user-owned units, so authoring a missing goal and re-matching recovers
    coverage on previously-unbound work without disturbing corrections."""
    if unit_graph is None or facet_source is None:
        raise HTTPException(status_code=503, detail="matcher seams not configured")
    n = await correlate_goal_facets(
        unit_graph=unit_graph,
        facet_source=facet_source,
        goal_graph=goal_graph,
        commitment_repository=commitment_repository,
        email_job_search_source=email_job_search_source,
        email_source_metadata=email_source_metadata,
        actor=actor,
    )
    return RematchResultDTO(evidence_edges=n)


@router.post("/cdd/evidence/unlink", status_code=204)
async def post_unlink_cdd_evidence(
    body: UnlinkCddEvidenceRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    unit_graph: Annotated[object | None, Depends(get_unit_graph)],
    audit_port: Annotated[object | None, Depends(get_cdd_audit_port)],
) -> Response:
    """Remove one of a unit's element bindings; mark the unit user-owned (D203)."""
    if unit_graph is None:
        raise HTTPException(status_code=503, detail="unit graph not configured")
    if body.kind not in EVIDENCE_KINDS:  # incl. "outcome" (S103c-fix-3)
        raise HTTPException(status_code=422, detail=f"unknown kind: {body.kind}")
    ok = await unlink_cdd_evidence(
        unit_graph=unit_graph, actor=actor, unit_id=body.unit_id,
        kind=body.kind, element_id=body.element_id, audit_port=audit_port,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="binding not found")
    return Response(status_code=204)


@router.post("/cdd/evidence/relink", status_code=204)
async def post_relink_cdd_evidence(
    body: RelinkCddEvidenceRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    unit_graph: Annotated[object | None, Depends(get_unit_graph)],
    audit_port: Annotated[object | None, Depends(get_cdd_audit_port)],
) -> Response:
    """Retarget one of a unit's element bindings to a different element; mark it
    user-corrected and the unit user-owned (D203)."""
    if unit_graph is None:
        raise HTTPException(status_code=503, detail="unit graph not configured")
    if body.from_kind not in EVIDENCE_KINDS or body.to_kind not in EVIDENCE_KINDS:
        raise HTTPException(status_code=422, detail="unknown element kind")
    ok = await relink_cdd_evidence(
        unit_graph=unit_graph, actor=actor, unit_id=body.unit_id,
        from_kind=body.from_kind, from_element_id=body.from_element_id,
        to_kind=body.to_kind, to_element_id=body.to_element_id, audit_port=audit_port,
    )
    if not ok:
        raise HTTPException(
            status_code=404, detail="binding or target element not found"
        )
    return Response(status_code=204)


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


@router.post("/cdd/elements/{kind}/{element_id}/reclassify", status_code=204)
async def post_reclassify_cdd_element(
    kind: ElementKind,
    element_id: UUID,
    body: ReclassifyCddElementRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Reclassify an authored element across types (D201, S103a). ``kind`` is the
    current type; the body's ``to_kind`` is the new one. Preserves identity, flips
    origin to user_authored, flags now-invalid incident edges (never drops them)."""
    try:
        to_kind = ElementKind(body.to_kind)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"unknown element kind: {body.to_kind}"
        )
    ok = await reclassify_cdd_element(
        goal_graph=goal_graph, actor=actor, from_kind=kind, to_kind=to_kind,
        element_id=element_id,
    )
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="authored element not found or no-op reclassify",
        )
    return Response(status_code=204)


@router.post("/cdd/{outcome_id}/outcome/accept", status_code=204)
async def post_accept_cdd_outcome(
    outcome_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Accept the authored outcome stance (proof on the terminal element, S103a)."""
    ok = await accept_cdd_outcome(
        goal_graph=goal_graph, actor=actor, outcome_id=outcome_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="no authored outcome to accept")
    return Response(status_code=204)


@router.post("/cdd/{outcome_id}/outcome/correct", status_code=204)
async def post_correct_cdd_outcome(
    outcome_id: UUID,
    body: CorrectCddElementRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Edit the authored outcome, flipping origin to user_authored (S103a, D200)."""
    await correct_cdd_outcome(
        goal_graph=goal_graph, actor=actor, outcome_id=outcome_id, label=body.label
    )
    return Response(status_code=204)


@router.post("/cdd/{outcome_id}/outcome/reject", status_code=204)
async def post_reject_cdd_outcome(
    outcome_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    goal_graph: Annotated[GoalGraphPort, Depends(get_goal_graph)],
) -> Response:
    """Clear the authored outcome stance — the user-initiated reject (S103a)."""
    ok = await reject_cdd_outcome(
        goal_graph=goal_graph, actor=actor, outcome_id=outcome_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="no authored outcome to clear")
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
    email_source_metadata: Annotated[
        object | None, Depends(get_email_source_metadata)
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
    """Serve the self-contained daily-driver operator surface (auth-exempt).

    ``no-store`` on the HTML: the surface is a single self-contained file whose
    inline JS changes every deploy, and ``FileResponse`` otherwise emits only an
    etag/last-modified (no ``Cache-Control``), so a browser can serve a stale
    copy and every fix reads as "no change" (the S103s relink loop). The surface
    is tiny and under active daily change; always fetch the current bytes."""
    return FileResponse(
        _PAGE_PATH,
        media_type="text/html",
        headers={"Cache-Control": "no-store, must-revalidate"},
    )


__all__ = ["router", "ui_router"]
