"""compose_daily_checkin — the outbound half of the check-in (D192, D194, S97b).

The composer fires once a day (on DAILY_SCHEDULED, riding the existing
FireTrigger idempotency): it discovers the eligible daily-cadence homeostatic
levers, sends the goal-level prompt, and creates the ``awaiting_report``
PendingClarification (``target_cell='checkin'``) carrying the scheduled beat
day and the eligible levers — so the operator's reply routes to the check-in
cell by the active-pending path (D140). ``create_pending_clarification`` expires
any prior PENDING first, holding the one-PENDING-per-user invariant (D134).

When the tenant has no eligible levers, the composer sends nothing — there is
nothing to check in on.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import uuid4

from shared_kernel import ActorContext

from contexts.audit.domain.ports import AuditPort
from contexts.messaging.api import (
    PendingClarificationRepository,
    create_pending_clarification,
)

from contexts.checkin.application.ports.eligible_levers import (
    EligibleLeversReader,
)
from contexts.checkin.application.ports.message_sender import (
    CheckinMessageSender,
)
from contexts.checkin.domain.checkin_message import build_checkin_message

_TARGET_CELL = "checkin"
# The reply opens Twilio's 24h window; the pending must outlive a same-day late
# reply, so a 23h TTL keeps the confirm round-trip inside one window.
_PENDING_TTL = timedelta(hours=23)


@dataclass(frozen=True)
class ComposeCheckinResult:
    """What the composer did (counts only; no PII)."""

    sent: bool
    lever_count: int
    goal_count: int


async def compose_daily_checkin(
    *,
    eligible_levers_reader: EligibleLeversReader,
    message_sender: CheckinMessageSender,
    pending_repository: PendingClarificationRepository,
    audit_port: AuditPort,
    actor: ActorContext,
    beat_date: date,
    originating_user_address: str,
    originating_channel: str = "WHATSAPP",
) -> ComposeCheckinResult:
    """Discover eligible levers, send the prompt, and open the pending."""
    levers = await eligible_levers_reader.list_eligible(actor=actor)
    if not levers:
        return ComposeCheckinResult(sent=False, lever_count=0, goal_count=0)

    message = build_checkin_message(levers)
    await message_sender.send(actor=actor, body=message)

    proposed_intent = {
        "stage": "awaiting_report",
        "beat_date": beat_date.isoformat(),
        "levers": [lever.to_dict() for lever in levers],
    }
    await create_pending_clarification(
        repository=pending_repository,
        audit_port=audit_port,
        actor=actor,
        user_id=actor.actor_id,
        originating_channel=originating_channel,
        originating_user_address=originating_user_address,
        originating_intake_id=uuid4(),
        proposed_intent=proposed_intent,
        proposed_action_summary=message,
        target_cell=_TARGET_CELL,
        ttl=_PENDING_TTL,
    )

    goal_ids = {lever.goal_id for lever in levers}
    return ComposeCheckinResult(
        sent=True, lever_count=len(levers), goal_count=len(goal_ids)
    )


__all__ = ["ComposeCheckinResult", "compose_daily_checkin"]
