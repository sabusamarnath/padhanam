"""IntakeRecord — the canonical-entry aggregate of the intake context (D127, D128).

An IntakeRecord is captured when work enters the platform, ahead of
any downstream portfolio write. D128 commits the intake-canonical
posture: every persisted state change at the platform's write
surfaces traces to an IntakeRecord via the ``intake_id`` field on
the persisted entity.

IntakeRecords are immutable — never updated or deleted — per the
"Originals never erased" principle.

``IntakeSource`` carries the single Phase 2-A value MANUAL_ENTRY;
CALENDAR_READ and EMAIL_READ activate at P14. ``IntakePayload`` is
a type alias over the source-specific payload value object — at
S44b the single ``ManualEntryPayload`` variant; it widens to a
Union when a second variant lands.

Domain code is framework-free per D16 — stdlib plus shared_kernel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID

from shared_kernel import ActorReference


class IntakeSource(str, Enum):
    """The provenance of an IntakeRecord (D127).

    Phase 2-A ships MANUAL_ENTRY only; CALENDAR_READ and EMAIL_READ
    activate at P14 per the deferred-decisions entry on intake
    sources beyond operator authority.
    """

    MANUAL_ENTRY = "MANUAL_ENTRY"


@dataclass(frozen=True)
class ManualEntryPayload:
    """The Phase 2-A ``IntakePayload`` variant — operator manual input.

    Carries the operator's raw text plus an optional free-text
    intent annotation and optional case associations. The
    ``linked_case_ids`` data structure lands at S44b; the
    linking-heuristics UX surface defers to P14.
    """

    raw_text: str
    intent_hint: str | None = None
    linked_case_ids: tuple[UUID, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.raw_text or not self.raw_text.strip():
            raise ValueError("ManualEntryPayload.raw_text must be non-empty")


# IntakePayload is a type alias over the source-specific payload value
# object. Single-variant at S44b; widens to a Union (ManualEntryPayload
# | CalendarReadPayload | EmailReadPayload) when P14 lands the second
# variant — a pure type-alias extension per the build-at-second-instance
# deferred-decisions discipline.
IntakePayload = ManualEntryPayload


@dataclass(frozen=True)
class IntakeRecord:
    """The canonical-entry aggregate root (D127, D128).

    Frozen — IntakeRecords are immutable once recorded. ``authored_by``
    is the persisted authoring identity (an ActorReference derived
    from the request-scoped ActorContext per D126).
    """

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    intake_source: IntakeSource
    payload: IntakePayload
    authored_by: ActorReference
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("IntakeRecord.jurisdiction must be non-empty")


__all__ = [
    "IntakePayload",
    "IntakeRecord",
    "IntakeSource",
    "ManualEntryPayload",
]
