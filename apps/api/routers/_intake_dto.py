"""Pydantic request/response DTOs for the intake HTTP surface (D127, D128).

The standalone intake routes — POST /api/v1/intakes plus the GET
single and list surfaces. ``RecordIntakeRequest`` carries the
manual-entry fields; ``IntakeResponse`` flattens the IntakeRecord
aggregate plus its ManualEntryPayload onto the wire.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from contexts.intake.domain import IntakeRecord
from contexts.intake.ports.intake_repository import IntakeListPage


class IntakeSourceEnum(str, Enum):
    """Wire mirror of the domain ``IntakeSource`` enum (D127)."""

    MANUAL_ENTRY = "MANUAL_ENTRY"


class RecordIntakeRequest(BaseModel):
    """Body for POST /api/v1/intakes."""

    intake_source: IntakeSourceEnum = IntakeSourceEnum.MANUAL_ENTRY
    raw_text: str = Field(min_length=1)
    intent_hint: str | None = None
    linked_case_ids: list[UUID] = Field(default_factory=list)


class IntakeResponse(BaseModel):
    """Wire shape of an IntakeRecord — the aggregate plus its payload."""

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    intake_source: str
    raw_text: str
    intent_hint: str | None
    linked_case_ids: list[UUID]
    authored_by_user_id: str
    created_at: datetime


class IntakeListResponse(BaseModel):
    """Envelope for GET /api/v1/intakes."""

    intakes: list[IntakeResponse]
    next_cursor: str | None = None


def intake_to_response(intake: IntakeRecord) -> IntakeResponse:
    return IntakeResponse(
        id=intake.id,
        tenant_id=intake.tenant_id,
        jurisdiction=intake.jurisdiction,
        intake_source=intake.intake_source.value,
        raw_text=intake.payload.raw_text,
        intent_hint=intake.payload.intent_hint,
        linked_case_ids=list(intake.payload.linked_case_ids),
        authored_by_user_id=intake.authored_by.user_id,
        created_at=intake.created_at,
    )


def intake_list_to_response(
    page: IntakeListPage, next_cursor: str | None
) -> IntakeListResponse:
    return IntakeListResponse(
        intakes=[intake_to_response(i) for i in page.intakes],
        next_cursor=next_cursor,
    )


__all__ = [
    "IntakeListResponse",
    "IntakeResponse",
    "IntakeSourceEnum",
    "RecordIntakeRequest",
    "intake_list_to_response",
    "intake_to_response",
]
