"""PendingClarification — multi-turn conversation state (D134, S47).

D134 commits PendingClarification as the multi-turn state the cell's
confidence-aware composition needs. At medium-confidence intent
classification the cell renders a shape-aware clarification and
persists the proposed action as a PendingClarification; the operator's
confirming reply resolves the pending and executes the proposed
action, a correcting reply resolves the pending as cancelled, and
silence times out at 24 hours per D119's WhatsApp Sandbox conversation
window.

*Scope per D136 Primitive 3.* The entity is scoped to
``(tenant_id, user_id)`` — at most one PENDING per tuple at a time.
``originating_channel`` and ``originating_user_address`` are
*metadata*; cross-channel reply resolution becomes possible at the
second-channel activation trigger when User-to-ChannelIdentity
mapping (D136 Primitive 1) lands. Phase 2-A's degenerate single-user
single-channel makes the scope question operationally invisible.

*D115 ConversationFlow Protocol unchanged.* The cell consults
PendingClarification via a consumer port at turn-open; the protocol
itself stays single-turn. Multi-turn behaviour emerges from the cell's
port-mediated state consultation.

Domain code is framework-free per D16 — stdlib plus shared_kernel.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class PendingClarificationStatus(str, Enum):
    """Lifecycle state of a PendingClarification.

    PENDING at creation; transitions to RESOLVED at the operator's
    confirming or correcting reply, or to EXPIRED when the 24-hour
    conversation window elapses without a reply.
    """

    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    EXPIRED = "EXPIRED"


# D140: target_cell identifiers the dispatch_inbound use case consults
# at active-pending routing. Four identifiers at P14 close; future
# ConversationFlow implementers at P15+ extend the set additively.
KNOWN_TARGET_CELLS: frozenset[str] = frozenset(
    {
        "manual_entry",
        "audit_conversation",
        "mirror_conversation",
        "dispatch_clarification",
    }
)


@dataclass(frozen=True)
class PendingClarification:
    """The multi-turn pending-clarification aggregate (D134, D140).

    Frozen — lifecycle transitions return a *new* instance with
    updated ``status`` and ``resolved_at``; mutation never happens
    in-place (matches the "Originals never erased" principle at
    Phase 2-A: each lifecycle event emits an audit row and the
    persistence layer carries the latest state).

    ``proposed_intent`` is the cell's structured best-guess intent at
    medium-confidence classification, held as a plain ``dict`` so
    callers can re-parse it through ``parse_intent`` when resolving.
    ``proposed_action_summary`` is the short human-readable phrasing
    of the proposed action the audit chain carries verbatim.

    ``target_cell`` (D140, S52) identifies which ConversationFlow
    implementer owns the pending. The dispatch_inbound use case
    consults this field on active-pending routing per D140's dispatch
    flow Step 2. Existing call sites at S47/S50 set this to
    ``"manual_entry"``; S51 audit-conversation sets ``"audit_conversation"``;
    S52 mirror-conversation sets ``"mirror_conversation"``; the meta-
    classification PendingClarification at D140 Step 5 sets
    ``"dispatch_clarification"``.
    """

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    user_id: str
    originating_channel: str
    originating_user_address: str
    originating_intake_id: UUID
    proposed_intent: dict[str, Any]
    proposed_action_summary: str
    status: PendingClarificationStatus
    target_cell: str
    created_at: datetime
    expires_at: datetime
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError(
                "PendingClarification.jurisdiction must be non-empty"
            )
        if not self.user_id.strip():
            raise ValueError(
                "PendingClarification.user_id must be non-empty"
            )
        if not self.originating_channel.strip():
            raise ValueError(
                "PendingClarification.originating_channel must be non-empty"
            )
        if not self.originating_user_address.strip():
            raise ValueError(
                "PendingClarification.originating_user_address must be non-empty"
            )
        if not self.proposed_action_summary.strip():
            raise ValueError(
                "PendingClarification.proposed_action_summary must be non-empty"
            )
        if self.target_cell not in KNOWN_TARGET_CELLS:
            raise ValueError(
                "PendingClarification.target_cell must be one of "
                f"{sorted(KNOWN_TARGET_CELLS)}; got {self.target_cell!r}"
            )
        if self.expires_at <= self.created_at:
            raise ValueError(
                "PendingClarification.expires_at must be strictly after created_at"
            )
        if (
            self.status is PendingClarificationStatus.PENDING
            and self.resolved_at is not None
        ):
            raise ValueError(
                "PendingClarification.resolved_at must be None while PENDING"
            )
        if (
            self.status is not PendingClarificationStatus.PENDING
            and self.resolved_at is None
        ):
            raise ValueError(
                "PendingClarification.resolved_at must be set on terminal status"
            )

    def resolve(self, *, at: datetime) -> "PendingClarification":
        """Return a RESOLVED copy of this pending."""
        if self.status is not PendingClarificationStatus.PENDING:
            raise ValueError(
                f"cannot resolve a {self.status.value} PendingClarification"
            )
        return PendingClarification(
            id=self.id,
            tenant_id=self.tenant_id,
            jurisdiction=self.jurisdiction,
            user_id=self.user_id,
            originating_channel=self.originating_channel,
            originating_user_address=self.originating_user_address,
            originating_intake_id=self.originating_intake_id,
            proposed_intent=self.proposed_intent,
            proposed_action_summary=self.proposed_action_summary,
            status=PendingClarificationStatus.RESOLVED,
            target_cell=self.target_cell,
            created_at=self.created_at,
            expires_at=self.expires_at,
            resolved_at=at,
        )

    def expire(self, *, at: datetime) -> "PendingClarification":
        """Return an EXPIRED copy of this pending."""
        if self.status is not PendingClarificationStatus.PENDING:
            raise ValueError(
                f"cannot expire a {self.status.value} PendingClarification"
            )
        return PendingClarification(
            id=self.id,
            tenant_id=self.tenant_id,
            jurisdiction=self.jurisdiction,
            user_id=self.user_id,
            originating_channel=self.originating_channel,
            originating_user_address=self.originating_user_address,
            originating_intake_id=self.originating_intake_id,
            proposed_intent=self.proposed_intent,
            proposed_action_summary=self.proposed_action_summary,
            status=PendingClarificationStatus.EXPIRED,
            target_cell=self.target_cell,
            created_at=self.created_at,
            expires_at=self.expires_at,
            resolved_at=at,
        )


__all__ = [
    "KNOWN_TARGET_CELLS",
    "PendingClarification",
    "PendingClarificationStatus",
]
