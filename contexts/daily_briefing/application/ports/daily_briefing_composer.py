"""DailyBriefingComposer consumer port — LLM summarisation (D130, D146, S54).

The daily-briefing implementer's LLM-call surface. The composer takes
the composed read inputs (briefing period plus the three producer-context
projections) and returns a prose narrative for the operator. Per D146 the
summarisation uses the StructuredOutputPort substrate (D130) at the
REAL_TIME_REQUIRED latency tier (D122); the LiteLLM-backed adapter lives
at ``contexts/daily_briefing/adapters/llm/``.

The empty-day case (no recent IntakeRecords or audit events; portfolio
state only) is handled by the composer's prompt template adjusting its
prose, not by skip logic at the implementer (D146). The composer always
returns a non-empty narrative.

The DTOs the composer consumes are the daily-briefing-owned
``DailyBriefingReader`` projections (DailyBriefingIntakeRecord,
DailyBriefingAuditEvent, DailyBriefingCase) — the composer does not reach
producer-context domain types.

Framework-free per D16 — stdlib plus shared_kernel only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from contexts.daily_briefing.application.ports.daily_briefing_reader import (
    DailyBriefingAuditEvent,
    DailyBriefingCase,
    DailyBriefingIntakeRecord,
)
from contexts.daily_briefing.domain.briefing_period import BriefingPeriod


@dataclass(frozen=True)
class DailyBriefingComposedContent:
    """The composer's output — the prose narrative for the briefing body.

    ``attention_items`` is reserved for the forward-looking escalation
    (S57 threshold-briefing); the Phase 2-A composer does not populate
    it (D146 Alternatives (b): heuristic attention-item guessing is
    rejected at first instance). The field defaults to an empty tuple
    so the structural shape is forward-compatible without forcing
    Phase 2-A population.
    """

    prose_narrative: str
    attention_items: tuple[str, ...] = ()


class DailyBriefingComposer(Protocol):
    """LLM summarisation port for the daily-briefing implementer (D146)."""

    async def compose(
        self,
        *,
        briefing_period: BriefingPeriod,
        intake_records: tuple[DailyBriefingIntakeRecord, ...],
        audit_events: tuple[DailyBriefingAuditEvent, ...],
        active_cases: tuple[DailyBriefingCase, ...],
    ) -> DailyBriefingComposedContent:
        """Compose the briefing prose from the window's reads.

        Always returns a non-empty narrative; the empty-day case is a
        prose adjustment at the prompt template, not a skip.
        """
        ...


__all__ = [
    "DailyBriefingComposedContent",
    "DailyBriefingComposer",
]
