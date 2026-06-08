"""HTTP DTOs for the daily-driver routes (D157, S58).

Response models mirror the domain value objects 1:1; request models
carry the minimal user-authored inputs. Pydantic v2 BaseModel, the
portfolio-DTO precedent.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from contexts.daily_driver.domain.commitment import OutcomeStatus
from contexts.daily_driver.domain.goal_view import ChainReading, GoalReading
from contexts.daily_driver.domain.today_item import (
    ItemKind,
    TodayItem,
    TodayView,
)


class TodayItemDTO(BaseModel):
    """One rendered row on the prioritised-today surface."""

    kind: str
    item_id: UUID
    title: str
    status: str
    target_cell: str
    artefact_type: str
    detail: str
    position: int | None
    done: bool
    overdue_by_days: int | None
    domain: str
    start_at: datetime | None
    # S61 (D162) — the expected-versus-observed loop on the row.
    expected_outcome: str | None
    observed_outcome: str | None
    outcome_status: str | None
    drop_candidate: bool


class TodayDTO(BaseModel):
    """The ordered prioritised-today list."""

    day_date: date
    items: list[TodayItemDTO]


class CommitmentDTO(BaseModel):
    """A user-authored Commitment."""

    id: UUID
    name: str
    expected_interval_days: int
    created_at: datetime
    expected_outcome: str | None = None
    observed_outcome: str | None = None
    outcome_status: str | None = None
    observed_at: datetime | None = None


class CompletionDTO(BaseModel):
    """One completion-log entry."""

    id: UUID
    commitment_id: UUID
    completed_at: datetime


class CreateCommitmentRequest(BaseModel):
    """Create a user-authored Commitment."""

    name: str = Field(min_length=1)
    expected_interval_days: int = Field(gt=0)
    # S61 (D162): the free-text expectation captured forward at creation.
    expected_outcome: str | None = None


class RecordObservedOutcomeRequest(BaseModel):
    """Record what transpired for a Commitment (D162).

    ``observed_outcome`` is free text (optional — a drop can carry no
    note); ``outcome_status`` is the coarse human-set status. Setting
    ``dropped`` is how the operator acts on a drop-candidate nudge.
    """

    observed_outcome: str | None = None
    outcome_status: OutcomeStatus


class ItemRef(BaseModel):
    """A (kind, id) reference to a today-item."""

    kind: ItemKind
    item_id: UUID


class SetOrderRequest(BaseModel):
    """The user's explicit ordering of today-items."""

    ordered: list[ItemRef]


class MarkDoneRequest(BaseModel):
    """Set or clear an item's done-for-today mark."""

    kind: ItemKind
    item_id: UUID
    done: bool


class GoalStepDTO(BaseModel):
    """One lever step in a sequence goal's chain view (D163, S63)."""

    name: str
    order: int
    state: str
    is_active: bool


class GoalReadingDTO(BaseModel):
    """A goal read against its lever(s) (D163).

    ``remedy_kind`` discriminates the shape: ``raise_or_hold`` (progressive) or
    ``unblock_or_drop`` (sequence). Progressive fields (``ladder``,
    ``current_target``, ``next_target``) are ``None`` for a sequence goal;
    sequence fields (``terminal_target``, ``terminal_state``, ``steps``,
    ``active_step``) are absent/empty for a progressive goal.
    """

    outcome_id: UUID
    name: str
    mode: str
    control: str
    subject: str
    remedy_kind: str
    # progressive (raise-or-hold)
    lever_commitment_id: UUID | None = None
    ladder: list[str] | None = None
    current_target: str | None = None
    next_target: str | None = None
    # sequence (unblock-or-drop)
    terminal_target: str | None = None
    terminal_state: str | None = None
    steps: list[GoalStepDTO] = []
    active_step: str | None = None
    # common
    progress_summary: str
    gap_summary: str
    recommendation: str
    reason: str


def goal_reading_to_dto(reading: GoalReading | ChainReading) -> GoalReadingDTO:
    """Encode a domain reading into the HTTP DTO, dispatching on shape (D163)."""
    if isinstance(reading, ChainReading):
        return _chain_reading_to_dto(reading)
    return _goal_reading_to_dto(reading)


def _goal_reading_to_dto(reading: GoalReading) -> GoalReadingDTO:
    goal = reading.goal
    return GoalReadingDTO(
        outcome_id=goal.id,
        name=goal.name,
        mode=goal.mode.value,
        control=goal.control.value,
        subject=goal.subject.value,
        remedy_kind="raise_or_hold",
        lever_commitment_id=goal.lever_commitment_id,
        ladder=list(goal.ladder.levels) if goal.ladder is not None else None,
        current_target=reading.current_target,
        next_target=reading.next_target,
        progress_summary=reading.progress_summary,
        gap_summary=reading.gap_summary,
        recommendation=reading.recommendation.value,
        reason=reading.reason,
    )


def _chain_reading_to_dto(reading: ChainReading) -> GoalReadingDTO:
    goal = reading.goal
    return GoalReadingDTO(
        outcome_id=goal.id,
        name=goal.name,
        mode=goal.mode.value,
        control=goal.control.value,
        subject=goal.subject.value,
        remedy_kind="unblock_or_drop",
        terminal_target=reading.terminal_target,
        terminal_state=reading.terminal_state,
        steps=[
            GoalStepDTO(
                name=s.name,
                order=s.order,
                state=s.state.value,
                is_active=s.is_active,
            )
            for s in reading.steps
        ],
        active_step=reading.active_step_name,
        progress_summary=reading.chain_summary,
        gap_summary=reading.chain_summary,
        recommendation=reading.recommendation.value,
        reason=reading.reason,
    )


def today_view_to_dto(view: TodayView) -> TodayDTO:
    """Encode a domain TodayView into the HTTP DTO."""
    return TodayDTO(
        day_date=view.day_date,
        items=[_item_to_dto(item) for item in view.items],
    )


def _item_to_dto(item: TodayItem) -> TodayItemDTO:
    return TodayItemDTO(
        kind=item.kind.value,
        item_id=item.item_id,
        title=item.title,
        status=item.status.value,
        target_cell=item.target_cell,
        artefact_type=item.artefact_type,
        detail=item.detail,
        position=item.position,
        done=item.done,
        overdue_by_days=item.overdue_by_days,
        domain=item.domain,
        start_at=item.start_at,
        expected_outcome=item.expected_outcome,
        observed_outcome=item.observed_outcome,
        outcome_status=item.outcome_status,
        drop_candidate=item.drop_candidate,
    )


__all__ = [
    "CommitmentDTO",
    "CompletionDTO",
    "CreateCommitmentRequest",
    "GoalReadingDTO",
    "GoalStepDTO",
    "ItemRef",
    "MarkDoneRequest",
    "RecordObservedOutcomeRequest",
    "SetOrderRequest",
    "TodayDTO",
    "TodayItemDTO",
    "goal_reading_to_dto",
    "today_view_to_dto",
]
