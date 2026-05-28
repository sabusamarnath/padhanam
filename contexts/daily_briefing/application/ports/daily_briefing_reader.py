"""DailyBriefingReader consumer port (D146, S54).

The daily-briefing implementer's cross-context read surface. Per
D16/D17/D28 the implementer cannot import producer-context application
modules directly; it consumes this consumer-defined Protocol, and the
``apps/`` composition root provides the wiring adapter that composes
the reads from three producer contexts (intake, audit, portfolio).

Third instance of the consumer-port-plus-wiring-adapter pattern
(PortfolioGateway at S46; MirrorPortfolioReader at S52; DailyBriefingReader
at S54) — and the first to compose *multiple* producer contexts behind
one consumer port.

The DTOs (``DailyBriefingIntakeRecord``, ``DailyBriefingAuditEvent``,
``DailyBriefingCase``) are daily-briefing-owned shapes the wiring
adapter translates producer-context entities into. Per S54 pre-write
reconciliation Finding 4, defining the DTOs here keeps the daily_briefing
application layer from importing producer-context domain modules,
preserving import-graph independence at the application-to-domain
cross-context surface (mirroring mirror-conversation's MirrorCaseSummary
discipline).

Framework-free per D16 — stdlib plus shared_kernel only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from shared_kernel import ActorContext


@dataclass(frozen=True)
class DailyBriefingIntakeRecord:
    """A recent IntakeRecord projected for the briefing composition."""

    intake_id: UUID
    intake_source: str
    summary: str
    created_at: datetime


@dataclass(frozen=True)
class DailyBriefingAuditEvent:
    """A recent audit event projected for the briefing composition."""

    event_id: UUID
    action_verb: str
    resource_type: str
    resource_id: str
    timestamp: datetime


@dataclass(frozen=True)
class DailyBriefingCase:
    """An active Case projected for the briefing's portfolio snapshot."""

    case_id: UUID
    title: str
    status: str
    created_at: datetime


class DailyBriefingReader(Protocol):
    """Read-side consumer port composing three producer contexts (D146).

    The wiring adapter at ``apps/api/_daily_briefing_wiring.py``
    delegates ``read_intake_records`` to the intake context's
    IntakeRepository, ``read_audit_events`` to the audit context's
    AuditEventReader, and ``read_active_cases`` to the portfolio
    context's list_cases use case.

    The window is a ``(start, end)`` tuple; ``read_active_cases`` takes
    no window because the portfolio snapshot is current-state, not
    window-scoped.
    """

    async def read_intake_records(
        self,
        *,
        actor: ActorContext,
        window: tuple[datetime, datetime],
    ) -> tuple[DailyBriefingIntakeRecord, ...]:
        """Recent IntakeRecords whose created_at falls inside the window."""
        ...

    async def read_audit_events(
        self,
        *,
        actor: ActorContext,
        window: tuple[datetime, datetime],
    ) -> tuple[DailyBriefingAuditEvent, ...]:
        """Recent audit events whose timestamp falls inside the window."""
        ...

    async def read_active_cases(
        self, *, actor: ActorContext
    ) -> tuple[DailyBriefingCase, ...]:
        """The operator's active Cases (current portfolio snapshot)."""
        ...


__all__ = [
    "DailyBriefingAuditEvent",
    "DailyBriefingCase",
    "DailyBriefingIntakeRecord",
    "DailyBriefingReader",
]
