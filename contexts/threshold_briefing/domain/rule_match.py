"""RuleMatch — a fired threshold crossing (D153, S57).

A ``RuleMatch`` is what the evaluator produces when a rule matches the
current calendar state. It carries the crossing identity (which seeds the
THRESHOLD_CROSSED idempotency key) and the displayable fields the
threshold-briefing composes from — so the briefing reads the crossing out
of the trigger metadata and never re-reads the store.

The crossing identity is derived-state, not an audit-event id (D153, the
S57 reconciliation): for a cancellation it is rule + event + cancelled_at;
for a conflict it is rule + the unordered pair of event ids. Same
one-brief-per-crossing guarantee as a matched-audit-event key, sourced
from the state instead.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from contexts.threshold_briefing.domain.threshold_rule import ThresholdRuleType


@dataclass(frozen=True)
class RuleMatch:
    """One threshold crossing the evaluator detected over calendar state.

    ``google_event_id``/``meeting_id``/``title`` identify the primary
    affected meeting (the cancelled meeting; the earlier-starting meeting
    of a conflicting pair). ``cancelled_at`` is set for a cancellation,
    ``None`` for a conflict. ``partner_event_id``/``partner_title`` carry
    the second meeting of a conflicting pair, ``None`` for a cancellation.
    ``summary`` is the human one-liner the briefing leads with.
    """

    rule_id: str
    rule_type: ThresholdRuleType
    google_event_id: str
    meeting_id: UUID
    title: str
    summary: str
    cancelled_at: datetime | None = None
    partner_event_id: str | None = None
    partner_title: str | None = None

    def crossing_identity(self) -> str:
        """Stable derived-state identity seeding the idempotency key (D153).

        Cancellation → ``rule_id:event:cancelled_at``. Conflict →
        ``rule_id:eventA|eventB`` with the pair sorted so the identity is
        order-independent (the same conflict found on two scans dedupes).
        """
        if self.partner_event_id is not None:
            pair = "|".join(sorted([self.google_event_id, self.partner_event_id]))
            return f"{self.rule_id}:{pair}"
        marker = self.cancelled_at.isoformat() if self.cancelled_at else ""
        return f"{self.rule_id}:{self.google_event_id}:{marker}"

    def to_trigger_metadata(self) -> dict[str, Any]:
        """Serialise the crossing into the THRESHOLD_CROSSED metadata dict.

        The emitter places this on the TriggerContext.metadata; the
        FireTrigger flow folds it into the BROADCAST_INITIATED after_state
        (procurement traceability of why the briefing fired); and the
        threshold-briefing reads it to compose without re-reading the store.
        """
        return {
            "rule_id": self.rule_id,
            "rule_type": self.rule_type.value,
            "google_event_id": self.google_event_id,
            "meeting_id": str(self.meeting_id),
            "title": self.title,
            "summary": self.summary,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else "",
            "partner_event_id": self.partner_event_id or "",
            "partner_title": self.partner_title or "",
            "crossing_identity": self.crossing_identity(),
        }


__all__ = ["RuleMatch"]
