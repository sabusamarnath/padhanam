"""record_intake_and_record_inbound_message orchestration (D128, D129).

The intake-canonical orchestration behind the Twilio WhatsApp
webhook receiver (POST ``/api/v1/messaging/inbound``). It records
an IntakeRecord first, then drives the inbound Message write through
the consumer-defined ``MessageWriter`` port with the ``intake_id``
propagated.

Placement at the intake context settles per D127 alternative (d):
intake-then-X orchestrations are one architectural concern and stay
at ``contexts/intake/application/``. This is the fourth such
orchestration after the three S44b portfolio orchestrations, and
the first whose downstream context is not portfolio — the consumer-
port pattern generalises across context-pairs unchanged.

Dual decorators (D126): the intake permission then the messaging
permission, so both authorisation checks fail-fast before any write
side effect.

Transaction semantics (D128): the orchestration writes across two
bounded contexts whose adapters each open their own per-call
transaction. The IntakeRecord writes first; if the downstream
Message write fails, the IntakeRecord persists as the canonical
record-of-attempt — structurally honest for the audit-trail
integrity argument.

The inbound-WhatsApp intake payload reuses ``ManualEntryPayload``
with ``raw_text`` carrying the message body, so the
``IntakePayload`` type alias stays single-variant per D127's
build-at-second-instance discipline.
"""

from __future__ import annotations

from contexts.audit.domain.ports import AuditPort

from contexts.intake.application.ports.message_writer import (
    MessageWriteResult,
    MessageWriter,
)
from contexts.intake.application.record_intake import record_intake
from contexts.intake.domain import IntakeSource, ManualEntryPayload
from contexts.intake.ports.intake_repository import IntakeRepository
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    INTAKE_RECORD_CREATE,
    MESSAGING_MESSAGE_RECEIVE,
    requires_authorisation,
)


@requires_authorisation(INTAKE_RECORD_CREATE)
@requires_authorisation(MESSAGING_MESSAGE_RECEIVE)
async def record_intake_and_record_inbound_message(
    *,
    intake_repository: IntakeRepository,
    audit_port: AuditPort,
    message_writer: MessageWriter,
    actor: ActorContext,
    channel: str,
    from_address: str,
    to_address: str,
    body: str,
    external_id: str | None = None,
) -> MessageWriteResult:
    """Record an intake, then persist the inbound Message it traces to."""
    intake = await record_intake(
        repository=intake_repository,
        audit_port=audit_port,
        actor=actor,
        intake_source=IntakeSource.WHATSAPP_INBOUND,
        payload=ManualEntryPayload(raw_text=body),
    )
    return await message_writer.record_inbound_message(
        actor=actor,
        channel=channel,
        from_address=from_address,
        to_address=to_address,
        body=body,
        external_id=external_id,
        intake_id=intake.id,
    )


__all__ = ["record_intake_and_record_inbound_message"]
