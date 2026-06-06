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
    "ItemRef",
    "MarkDoneRequest",
    "RecordObservedOutcomeRequest",
    "SetOrderRequest",
    "TodayDTO",
    "TodayItemDTO",
    "today_view_to_dto",
]
