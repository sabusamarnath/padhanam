"""Case — the aggregate root of the portfolio context (D124).

A Case is a unit of portfolio state — at Phase 2-A, a
``PORTFOLIO_ITEM``. It is the aggregate root; DataPoints (goals,
statuses, methodology applications) and their Assertions live
within its boundary. ``status`` is mutable — OPEN to CLOSED or
ARCHIVED — and per the "Originals never erased" principle a Case
is archived, never deleted, in normal operation.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class CaseType(str, Enum):
    """Case kind (D124). Phase 2-A ships ``PORTFOLIO_ITEM`` only."""

    PORTFOLIO_ITEM = "PORTFOLIO_ITEM"


class CaseStatus(str, Enum):
    """Case lifecycle status (D124)."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class Case:
    """The portfolio-context aggregate root (D124)."""

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    title: str
    case_type: CaseType
    status: CaseStatus
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must be non-empty")
        if not self.title.strip():
            raise ValueError("title must be non-empty")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")


__all__ = ["Case", "CaseStatus", "CaseType"]
