"""Commitment — the minimal user-authored cadence (D157, D162).

A ``Commitment`` is a name plus an expected interval in days; its
``CommitmentCompletion`` log records each time the user marks it done.
Staleness (overdue) is computed at render from elapsed-since-last-
completion against the interval — never persisted (D157). The full
cadence-with-staleness primitive (threshold-engine integration,
multiple cadence types, richer completion semantics) defers to Phase
2-B per the deferred-decisions "Cadence-with-staleness primitive (full)"
entry.

S61 (D162) extends the record with the minimal expected-versus-observed
loop: a free-text ``expected_outcome`` captured forward at creation, a
free-text ``observed_outcome`` captured after with a coarse
``outcome_status``, and the ``observed_at`` timestamp of that capture.
These are fields on the Commitment record (D162), not extensions of the
completion log: the completion log is the cadence-tick history, while the
expected/observed pair is about the commitment as a whole. The gap is a
view-time comparison; the LLM-computed gap, the graph causal edges, and
the longitudinal optimisation are deferred behind the dogfooding verdict.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from uuid import UUID


class OutcomeStatus(str, Enum):
    """Coarse human-set status of the expected-versus-observed gap (D162).

    Set when the user records an observation; ``None`` on the Commitment
    until then (no "pending" value — absence is the not-yet-observed
    state). ``DROPPED`` is how the operator acts on a drop-candidate
    recommendation (the no-auto-deletion path).
    """

    MET = "met"
    PARTIAL = "partial"
    MISSED = "missed"
    CHANGED = "changed"
    DROPPED = "dropped"


@dataclass(frozen=True)
class Commitment:
    """A user-authored recurring commitment (D157, D162)."""

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    name: str
    expected_interval_days: int
    authored_by_user_id: str
    created_at: datetime
    expected_outcome: str | None = None
    observed_outcome: str | None = None
    outcome_status: OutcomeStatus | None = None
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must be non-empty")
        if not self.name.strip():
            raise ValueError("name must be non-empty")
        if not self.authored_by_user_id.strip():
            raise ValueError("authored_by_user_id must be non-empty")
        if self.expected_interval_days <= 0:
            raise ValueError("expected_interval_days must be positive")
        if self.observed_outcome is not None and self.outcome_status is None:
            raise ValueError(
                "outcome_status must be set when observed_outcome is recorded"
            )


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


class CheckinOutcome(str, Enum):
    """A per-commitment check-in outcome (D192).

    ``DID`` is a completion (the beat is hit); ``REPORTED_DIDNT`` is a
    tracked negative (the beat is missed *with evidence*). Silence is the
    absence of a response, never a value here.
    """

    DID = "did"
    REPORTED_DIDNT = "reported_didnt"


@dataclass(frozen=True)
class CheckinResponse:
    """One check-in response against a commitment for a beat date (D192).

    The sibling-store record that makes the negative first-class. Under the
    Option-B did-source (D192), dids keep flowing to the ``CommitmentCompletion``
    log; this store carries the ``REPORTED_DIDNT`` negatives the cadence read
    consults for ``last_reported_didnt``. ``beat_date`` is the day the outcome
    refers to (backfillable — a past date is accepted).
    """

    id: UUID
    commitment_id: UUID
    tenant_id: UUID
    jurisdiction: str
    beat_date: date
    outcome: CheckinOutcome

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must be non-empty")


@dataclass(frozen=True)
class CommitmentActivity:
    """A Commitment paired with its most recent completion and reported miss.

    ``last_completed_at`` is ``None`` when the commitment has never been
    completed. ``last_reported_didnt`` (D192) is the most recent beat the
    operator reported *not* doing — a tracked negative, distinct from silence
    (also ``None``). The three-state cadence read consults both: a did reads
    the cadence verdict, a more-recent reported-didn't reads behind/stalled with
    evidence, neither reads not-tracked.
    """

    commitment: Commitment
    last_completed_at: datetime | None
    last_reported_didnt: date | None = None


__all__ = [
    "CheckinOutcome",
    "CheckinResponse",
    "Commitment",
    "CommitmentActivity",
    "CommitmentCompletion",
    "OutcomeStatus",
]
