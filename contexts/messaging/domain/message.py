"""Message — the aggregate root of the messaging bounded context (D129).

A Message is one inbound or outbound communication on a channel.
Phase 2-A ships the WhatsApp channel via the Twilio Sandbox per
D119; D129 commits this bounded-context substrate.

Messages are immutable once persisted, per the "Originals never
erased" principle. An outbound Message is created QUEUED and the
delivery adapter reports the vendor's accepted status; an inbound
Message is RECEIVED. ``intake_id`` traces an inbound Message to the
IntakeRecord the ``record_intake_and_record_inbound_message``
orchestration recorded (D128); an outbound Message carries none.

Domain code is framework-free per D16 — stdlib plus shared_kernel.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class MessageDirection(str, Enum):
    """Whether a Message flows into or out of the platform."""

    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class MessageChannel(str, Enum):
    """The messaging channel a Message travels on.

    Phase 2-A ships ``WHATSAPP`` only (D119: WhatsApp via the Twilio
    Sandbox). SMS, voice, and email channels extend the enum at P14+
    per the channel-enum extension trigger.
    """

    WHATSAPP = "WHATSAPP"


class MessageStatus(str, Enum):
    """The delivery lifecycle state of a Message.

    Outbound: ``QUEUED`` at creation, ``SENT`` once the vendor
    accepts, ``DELIVERED`` once the vendor confirms delivery,
    ``FAILED`` on a rejected send. Inbound: ``RECEIVED``.
    """

    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    RECEIVED = "RECEIVED"


@dataclass(frozen=True)
class Message:
    """The messaging aggregate root (D129).

    Frozen — Messages are immutable once recorded. ``actor_id`` is
    the acting actor's identity; ``external_id`` is the vendor
    message identifier, unset until the vendor assigns one;
    ``intake_id`` is the IntakeRecord an inbound Message traces to
    per D128 and is ``None`` on an outbound Message.
    """

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    direction: MessageDirection
    channel: MessageChannel
    body: str
    from_address: str
    to_address: str
    status: MessageStatus
    actor_id: str
    created_at: datetime
    external_id: str | None = None
    intake_id: UUID | None = None

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("Message.jurisdiction must be non-empty")
        if not self.body.strip():
            raise ValueError("Message.body must be non-empty")
        if not self.from_address.strip():
            raise ValueError("Message.from_address must be non-empty")
        if not self.to_address.strip():
            raise ValueError("Message.to_address must be non-empty")
        if not self.actor_id.strip():
            raise ValueError("Message.actor_id must be non-empty")
        if (
            self.direction is MessageDirection.OUTBOUND
            and self.intake_id is not None
        ):
            raise ValueError(
                "Message.intake_id must be None on an OUTBOUND message"
            )


__all__ = [
    "Message",
    "MessageChannel",
    "MessageDirection",
    "MessageStatus",
]
