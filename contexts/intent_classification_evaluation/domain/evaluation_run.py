"""EvaluationRun aggregate root for intent-classification evaluation (D137, S48b).

Mirrors the P11 ``contexts.retrieval_evaluation.domain.evaluation_run``
shape (status lifecycle, started_at, completed_at) with shape-
specific fields for intent classification (gold_set_name,
model_identifier per D132's four-layer ontology).

Per D110 audit-event-level tamper-evidence absorption, every write
to the evaluation-substrate tables emits an audit event chained
into the tenant audit chain; this aggregate does not carry a
parallel hash chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from shared_kernel.inference import ModelIdentifier


class EvaluationRunStatus(StrEnum):
    """Status lifecycle for an evaluation run.

    Transitions: ``running`` is the genesis state when the runner
    starts; ``completed`` marks a successful finish where all entries
    were classified; ``failed`` marks an unrecoverable failure during
    the run (e.g., inference adapter raised a non-parse exception
    the runner could not absorb per-entry).
    """

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class EvaluationRun:
    """An EvaluationRun records one model's classifications against one gold set.

    ``id`` is the run's UUID. ``tenant_id`` carries the per-tenant
    scope (every evaluation run sits inside one tenant's audit chain
    even though the substrate is operator-dogfooding at Phase 2-A).
    ``gold_set_name`` references the gold-set used; the YAML fixture's
    name is the canonical reference at Phase 2-A. ``model_identifier``
    is the four-layer model ontology per D132 capturing the exact
    provider/account/version/configuration evaluated.
    """

    id: UUID
    tenant_id: UUID
    gold_set_name: str
    model_identifier: ModelIdentifier
    status: EvaluationRunStatus
    started_at: datetime
    completed_at: datetime | None
    failure_reason: str | None

    def __post_init__(self) -> None:
        if not self.gold_set_name or not self.gold_set_name.strip():
            raise ValueError("EvaluationRun.gold_set_name must be non-empty")
        if self.started_at.tzinfo is None:
            raise ValueError("EvaluationRun.started_at must be tz-aware")
        if self.completed_at is not None and self.completed_at.tzinfo is None:
            raise ValueError("EvaluationRun.completed_at must be tz-aware")
        if self.status is EvaluationRunStatus.RUNNING and (
            self.completed_at is not None or self.failure_reason is not None
        ):
            raise ValueError(
                "EvaluationRun.completed_at and failure_reason must be null "
                "when status is running"
            )
        if self.status is EvaluationRunStatus.COMPLETED and (
            self.completed_at is None or self.failure_reason is not None
        ):
            raise ValueError(
                "EvaluationRun.completed_at must be set and failure_reason "
                "must be null when status is completed"
            )
        if self.status is EvaluationRunStatus.FAILED and (
            self.completed_at is None or not (self.failure_reason or "").strip()
        ):
            raise ValueError(
                "EvaluationRun.completed_at and failure_reason must both be "
                "set when status is failed"
            )

    def mark_completed(self, *, at: datetime) -> "EvaluationRun":
        """Transition running -> completed; new value object returned."""
        if self.status is not EvaluationRunStatus.RUNNING:
            raise ValueError(
                f"EvaluationRun.mark_completed requires running status; "
                f"got {self.status}"
            )
        if at.tzinfo is None:
            raise ValueError("EvaluationRun.mark_completed at must be tz-aware")
        return EvaluationRun(
            id=self.id,
            tenant_id=self.tenant_id,
            gold_set_name=self.gold_set_name,
            model_identifier=self.model_identifier,
            status=EvaluationRunStatus.COMPLETED,
            started_at=self.started_at,
            completed_at=at,
            failure_reason=None,
        )

    def mark_failed(self, *, at: datetime, reason: str) -> "EvaluationRun":
        """Transition running -> failed; new value object returned."""
        if self.status is not EvaluationRunStatus.RUNNING:
            raise ValueError(
                f"EvaluationRun.mark_failed requires running status; "
                f"got {self.status}"
            )
        if not reason or not reason.strip():
            raise ValueError("EvaluationRun.mark_failed reason must be non-empty")
        if at.tzinfo is None:
            raise ValueError("EvaluationRun.mark_failed at must be tz-aware")
        return EvaluationRun(
            id=self.id,
            tenant_id=self.tenant_id,
            gold_set_name=self.gold_set_name,
            model_identifier=self.model_identifier,
            status=EvaluationRunStatus.FAILED,
            started_at=self.started_at,
            completed_at=at,
            failure_reason=reason,
        )


def utcnow() -> datetime:
    """tz-aware now() helper for run timestamps."""
    return datetime.now(timezone.utc)


__all__ = [
    "EvaluationRun",
    "EvaluationRunStatus",
    "utcnow",
]
