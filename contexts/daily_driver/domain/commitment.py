"""Commitment — the minimal user-authored cadence (D157).

A ``Commitment`` is a name plus an expected interval in days; its
``CommitmentCompletion`` log records each time the user marks it done.
Staleness (overdue) is computed at render from elapsed-since-last-
completion against the interval — never persisted (D157). The full
cadence-with-staleness primitive (threshold-engine integration,
multiple cadence types, richer completion semantics) defers to Phase
2-B per the deferred-decisions "Cadence-with-staleness primitive (full)"
entry.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Commitment:
    """A user-authored recurring commitment (D157)."""

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    name: str
    expected_interval_days: int
    authored_by_user_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must be non-empty")
        if not self.name.strip():
            raise ValueError("name must be non-empty")
        if not self.authored_by_user_id.strip():
            raise ValueError("authored_by_user_id must be non-empty")
        if self.expected_interval_days <= 0:
            raise ValueError("expected_interval_days must be positive")


@dataclass(frozen=True)
class CommitmentCompletion:
    """One entry in a Commitment's completion log (D157)."""

    id: UUID
    commitment_id: UUID
    tenant_id: UUID
    jurisdiction: str
    completed_at: datetime

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must be non-empty")


@dataclass(frozen=True)
class CommitmentActivity:
    """A Commitment paired with its most recent completion time.

    ``last_completed_at`` is ``None`` when the commitment has never been
    completed; the staleness rule then measures elapsed time from
    ``commitment.created_at``.
    """

    commitment: Commitment
    last_completed_at: datetime | None


__all__ = ["Commitment", "CommitmentActivity", "CommitmentCompletion"]
