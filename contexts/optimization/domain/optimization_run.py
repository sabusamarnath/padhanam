"""OptimizationRun aggregate root (D111 commitment 2).

The engine-invocation aggregate that orchestrates rule iteration
against the EvidenceContext, persists candidates as Recommendation
rows linked via FK, and captures any rule skip-reasons on the
``skipped_categories`` field. Substrate-symmetric with the
EvaluationRun aggregate at retrieval_evaluation per D111 cmt 2 — both
contexts ship engine-shaped invocations producing outputs against
evidence; aligning the shape at substrate time avoids the
methodology-candidate observation P12 would pick up otherwise.

Per D111 commitment 2 the parent aggregate is mutable for status
transitions (``running`` → ``completed`` or ``failed``); the engine
writes a `running` row at invocation, iterates registered rules,
persists candidates as Recommendation rows, captures any skip-
reasons on this aggregate's ``skipped_categories`` field, marks
status `completed` on success or `failed` on uncaught exception.

The ``skipped_categories`` field carries Phase 1 substrate-gap
transparency for model_choice and prompt_revision (their substrate,
scoring-sheet evaluation runs from contexts/evaluation/, is Phase 2
territory). Shape: ``{category: {reason_code, reason_text}}`` —
queryable downstream so procurement readers can see which
categories the engine deliberately skipped this invocation and why.

Domain code is framework-free per D16 — stdlib dataclasses only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping
from uuid import UUID


class OptimizationRunStatus(str, Enum):
    """OptimizationRun lifecycle (D111 commitment 2)."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class CategorySkipReason:
    """Structured skip-reason on the OptimizationRun aggregate.

    Captured when a rule's substrate is unavailable (Phase 1: model_choice
    and prompt_revision per D111 commitment 5). reason_code is queryable
    downstream; reason_text is the human-readable transparency message
    the CLI and Phase 2 UX render.
    """

    reason_code: str
    reason_text: str


@dataclass(frozen=True)
class OptimizationRun:
    """OptimizationRun aggregate root.

    Carries the invocation actor, lifecycle timestamps, status, and
    the structured skip-reasons captured during rule iteration.
    ``completed_at`` is nullable until status transitions to a
    terminal value. The dataclass is frozen for value-semantic
    equality; status transitions produce new instances per the
    aggregate-with-status-lifecycle precedent from D110 commitment 2.
    """

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    invoked_by_user_id: str
    invoked_at: datetime
    completed_at: datetime | None
    status: OptimizationRunStatus
    skipped_categories: Mapping[str, CategorySkipReason] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must be non-empty")
        if not self.invoked_by_user_id.strip():
            raise ValueError("invoked_by_user_id must be non-empty")
        if self.status is OptimizationRunStatus.RUNNING:
            if self.completed_at is not None:
                raise ValueError(
                    "completed_at must be None while status is running"
                )
        else:
            if self.completed_at is None:
                raise ValueError(
                    f"completed_at must be set on terminal status "
                    f"{self.status.value}"
                )

    @property
    def is_terminal(self) -> bool:
        return self.status is not OptimizationRunStatus.RUNNING


__all__ = [
    "CategorySkipReason",
    "OptimizationRun",
    "OptimizationRunStatus",
]
