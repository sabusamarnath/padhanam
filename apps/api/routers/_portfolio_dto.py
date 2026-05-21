"""Pydantic response DTOs for the portfolio HTTP routes (D124, S43b).

Field-for-field mirror of the portfolio domain entities. The
``ActorReference`` value object surfaces as its flattened
``authored_by_user_id`` string on the wire; enums surface as their
string values; ``value`` JSONB surfaces as ``dict[str, Any]``.
Mapping helpers convert domain entities to DTOs explicitly — the
``ActorReference`` nesting and the ``CaseDetail`` composite make
explicit mapping clearer than ``model_validate`` here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from contexts.portfolio.application.get_case_detail import CaseDetail
from contexts.portfolio.domain import Assertion, Case, DataPoint
from contexts.portfolio.ports import CaseListPage


class AssertionDTO(BaseModel):
    """Mirrors ``Assertion`` per D124."""

    id: UUID
    data_point_id: UUID
    tenant_id: UUID
    jurisdiction: str
    assertion_type: str
    revises_assertion_id: UUID | None
    value: dict[str, Any]
    authored_by_user_id: str
    created_at: datetime


class DataPointDTO(BaseModel):
    """Mirrors ``DataPoint`` per D124, with the revision history embedded."""

    id: UUID
    case_id: UUID
    tenant_id: UUID
    jurisdiction: str
    data_point_type: str
    value: dict[str, Any]
    authored_by_user_id: str
    certainty: float | None
    created_at: datetime
    current_value: dict[str, Any]
    assertions: list[AssertionDTO]


class CaseDTO(BaseModel):
    """Mirrors ``Case`` per D124."""

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    title: str
    case_type: str
    status: str
    created_at: datetime
    updated_at: datetime


class CaseListDTO(BaseModel):
    """Envelope for ``GET /api/v1/portfolio/cases``.

    Carries the page of cases plus the opaque next-cursor string when
    more pages exist; the consumer treats the cursor as a black box.
    """

    cases: list[CaseDTO]
    next_cursor: str | None = None


class CaseDetailDTO(BaseModel):
    """Envelope for ``GET /api/v1/portfolio/cases/{case_id}`` — a Case
    plus its DataPoints, each carrying its full revision history."""

    case: CaseDTO
    data_points: list[DataPointDTO]


def assertion_to_dto(assertion: Assertion) -> AssertionDTO:
    return AssertionDTO(
        id=assertion.id,
        data_point_id=assertion.data_point_id,
        tenant_id=assertion.tenant_id,
        jurisdiction=assertion.jurisdiction,
        assertion_type=assertion.assertion_type.value,
        revises_assertion_id=assertion.revises_assertion_id,
        value=assertion.value,
        authored_by_user_id=assertion.authored_by.user_id,
        created_at=assertion.created_at,
    )


def data_point_to_dto(data_point: DataPoint) -> DataPointDTO:
    return DataPointDTO(
        id=data_point.id,
        case_id=data_point.case_id,
        tenant_id=data_point.tenant_id,
        jurisdiction=data_point.jurisdiction,
        data_point_type=data_point.data_point_type.value,
        value=data_point.value,
        authored_by_user_id=data_point.authored_by.user_id,
        certainty=data_point.certainty,
        created_at=data_point.created_at,
        current_value=data_point.current_value,
        assertions=[assertion_to_dto(a) for a in data_point.assertions],
    )


def case_to_dto(case: Case) -> CaseDTO:
    return CaseDTO(
        id=case.id,
        tenant_id=case.tenant_id,
        jurisdiction=case.jurisdiction,
        title=case.title,
        case_type=case.case_type.value,
        status=case.status.value,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def case_list_to_dto(
    page: CaseListPage, next_cursor: str | None
) -> CaseListDTO:
    return CaseListDTO(
        cases=[case_to_dto(c) for c in page.cases],
        next_cursor=next_cursor,
    )


def case_detail_to_dto(detail: CaseDetail) -> CaseDetailDTO:
    return CaseDetailDTO(
        case=case_to_dto(detail.case),
        data_points=[data_point_to_dto(dp) for dp in detail.data_points],
    )


__all__ = [
    "AssertionDTO",
    "CaseDTO",
    "CaseDetailDTO",
    "CaseListDTO",
    "DataPointDTO",
    "assertion_to_dto",
    "case_detail_to_dto",
    "case_list_to_dto",
    "case_to_dto",
    "data_point_to_dto",
]
