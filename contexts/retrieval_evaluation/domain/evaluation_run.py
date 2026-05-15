"""Evaluation-run aggregate root (D110 commitment 2).

The evaluation run is the parent aggregate the retrieval-evaluation
runner orchestrates: a single run exercises every entry in one
gold-set revision against every retrieval strategy that has an
executing branch in ``AgentRetrievalClientAdapter`` at S40 close
(``vector_only`` and ``graph_only``; ``parallel_rrf`` deferred per
``charter/deferred-decisions.md``), producing per-query
``EvaluationResult`` records and per-strategy ``EvaluationAggregate``
records.

Per D110 commitment 2 the parent aggregate is mutable for status
transitions (``running`` → ``completed`` or ``failed``) per the
aggregate-with-status-lifecycle pattern from the methodology context;
the child records (``EvaluationResult`` and ``EvaluationAggregate``)
are append-only and immutable.

Domain code is framework-free per D16 — stdlib dataclasses only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class EvaluationRunStatus(str, Enum):
    """Run lifecycle (D110 commitment 2).

    A run starts in ``running`` at orchestration begin; the runner
    transitions to ``completed`` on successful aggregate computation
    at run-end, or to ``failed`` if any per-query or per-strategy
    step raises uncaught. Completed and failed are terminal; once
    set, the run does not mutate further.
    """

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class EvaluationRun:
    """Evaluation-run aggregate root.

    Carries the gold-set revision reference captured at invocation
    time (so revision drift between invocation and authoring is
    auditable per D110 commitment 2), the invocation actor, and the
    lifecycle timestamps. ``completed_at`` is nullable until the
    status transitions to a terminal value.

    The dataclass is frozen for value-semantic equality; status
    transitions produce new instances rather than mutating in place,
    keeping the application layer's intent visible in the type
    system per the methodology/role aggregate precedent.
    """

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    gold_set_id: UUID
    gold_set_revision_id: UUID
    invoked_by_user_id: str
    invoked_at: datetime
    completed_at: datetime | None
    status: EvaluationRunStatus

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must be non-empty")
        if not self.invoked_by_user_id.strip():
            raise ValueError("invoked_by_user_id must be non-empty")
        if self.status is EvaluationRunStatus.RUNNING:
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
        return self.status is not EvaluationRunStatus.RUNNING
