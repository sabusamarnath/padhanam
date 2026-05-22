"""Pydantic request/response DTOs for the portfolio write surface (D127, D128).

S44b splits the portfolio DTO module: the read DTOs stay at
``_portfolio_dto.py``; the write DTOs land here, ahead of the
``_portfolio_dto.py`` 300-line split trigger (S44b file-topology
budget). Each write DTO carries the intake side (``raw_text``,
``intent_hint``, ``linked_case_ids``) the orchestration records as a
ManualEntryPayload, plus the portfolio side. Responses surface the
``intake_id`` the write traces to per D128.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from contexts.intake.application.ports.portfolio_writer import (
    CaseWriteResult,
    DataPointWriteResult,
)
from contexts.portfolio.domain import DataPointType


class _IntakeFields(BaseModel):
    """The manual-entry intake fields shared by every write request."""

    raw_text: str = Field(min_length=1)
    intent_hint: str | None = None
    linked_case_ids: list[UUID] = Field(default_factory=list)


class CreateCaseRequest(_IntakeFields):
    """Body for POST /api/v1/cases."""

    title: str = Field(min_length=1)


class CreateCaseResponse(BaseModel):
    """201 body for POST /api/v1/cases — the created Case plus intake_id."""

    case_id: UUID
    tenant_id: UUID
    jurisdiction: str
    title: str
    case_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    intake_id: UUID


class CreateDataPointRequest(_IntakeFields):
    """Body for POST /api/v1/data_points."""

    case_id: UUID
    data_point_type: DataPointType
    value: dict[str, Any]


class CreateDataPointResponse(BaseModel):
    """201 body for POST /api/v1/data_points."""

    data_point_id: UUID
    case_id: UUID
    data_point_type: str
    current_value: dict[str, Any]
    initial_assertion_id: UUID
    intake_id: UUID


class ReviseDataPointRequest(_IntakeFields):
    """Body for PATCH /api/v1/data_points/{data_point_id}."""

    value: dict[str, Any]


class ReviseDataPointResponse(BaseModel):
    """200 body for PATCH /api/v1/data_points/{data_point_id}."""

    data_point_id: UUID
    latest_assertion_id: UUID
    revision_count: int
    current_value: dict[str, Any]
    intake_id: UUID


def case_write_result_to_response(
    result: CaseWriteResult,
) -> CreateCaseResponse:
    return CreateCaseResponse(
        case_id=result.case_id,
        tenant_id=result.tenant_id,
        jurisdiction=result.jurisdiction,
        title=result.title,
        case_type=result.case_type,
        status=result.status,
        created_at=result.created_at,
        updated_at=result.updated_at,
        intake_id=result.intake_id,
    )


def data_point_create_result_to_response(
    result: DataPointWriteResult,
) -> CreateDataPointResponse:
    return CreateDataPointResponse(
        data_point_id=result.data_point_id,
        case_id=result.case_id,
        data_point_type=result.data_point_type,
        current_value=result.current_value,
        initial_assertion_id=result.assertion_ids[0],
        intake_id=result.intake_id,
    )


def data_point_revise_result_to_response(
    result: DataPointWriteResult,
) -> ReviseDataPointResponse:
    return ReviseDataPointResponse(
        data_point_id=result.data_point_id,
        latest_assertion_id=result.assertion_ids[-1],
        revision_count=len(result.assertion_ids),
        current_value=result.current_value,
        intake_id=result.intake_id,
    )


__all__ = [
    "CreateCaseRequest",
    "CreateCaseResponse",
    "CreateDataPointRequest",
    "CreateDataPointResponse",
    "ReviseDataPointRequest",
    "ReviseDataPointResponse",
    "case_write_result_to_response",
    "data_point_create_result_to_response",
    "data_point_revise_result_to_response",
]
