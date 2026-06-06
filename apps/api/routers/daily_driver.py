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
    MarkDoneRequest,
    RecordObservedOutcomeRequest,
    SetOrderRequest,
    TodayDTO,
    today_view_to_dto,
)
from contexts.daily_driver.application import (
    create_commitment,
    list_today,
    log_commitment_completion,
    mark_item_done,
    record_observed_outcome,
    set_today_order,
)
from contexts.daily_driver.domain.commitment import Commitment
from contexts.daily_driver.ports import (
    CalendarEventsReader,
    CommitmentRepository,
    DayRepository,
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
    )
    return Response(status_code=204)


@ui_router.get("/app", include_in_schema=False)
async def daily_driver_page() -> FileResponse:
    """Serve the self-contained daily-driver operator surface (auth-exempt)."""
    return FileResponse(_PAGE_PATH, media_type="text/html")


__all__ = ["router", "ui_router"]
