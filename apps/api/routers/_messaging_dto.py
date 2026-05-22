"""Pydantic request/response DTOs for the messaging HTTP surface (D129).

Four routes — the outbound send, the inbound Twilio webhook, plus
the GET single and list surfaces. ``MessageResponse`` flattens the
Message aggregate onto the wire; ``InboundWebhookAck`` is the small
2xx acknowledgement the Twilio webhook receiver returns (Twilio
needs a 2xx, not a body).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from contexts.intake.application.ports.message_writer import (
    MessageWriteResult,
)
from contexts.messaging.domain import Message
from contexts.messaging.ports.message_repository import MessageListPage


class SendMessageRequest(BaseModel):
    """Body for POST /api/v1/messaging/send.

    The operator supplies the recipient and the body; the platform's
    WhatsApp sender address and the WHATSAPP channel are resolved
    from configuration, not the request.
    """

    to_address: str = Field(min_length=1)
    body: str = Field(min_length=1)


class MessageResponse(BaseModel):
    """Wire shape of a Message — the aggregate flattened."""

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    direction: str
    channel: str
    body: str
    from_address: str
    to_address: str
    status: str
    external_id: str | None
    intake_id: UUID | None
    actor_id: str
    created_at: datetime


class MessageListResponse(BaseModel):
    """Envelope for GET /api/v1/messaging/messages."""

    messages: list[MessageResponse]
    next_cursor: str | None = None


class InboundWebhookAck(BaseModel):
    """Acknowledgement body for the Twilio inbound webhook.

    Twilio needs only a 2xx; the body carries the recorded ids so the
    live-stack smoke and the integration tests can assert the inbound
    message landed as both an IntakeRecord and a Message.
    """

    status: str
    message_id: UUID
    intake_id: UUID


def message_to_response(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        tenant_id=message.tenant_id,
        jurisdiction=message.jurisdiction,
        direction=message.direction.value,
        channel=message.channel.value,
        body=message.body,
        from_address=message.from_address,
        to_address=message.to_address,
        status=message.status.value,
        external_id=message.external_id,
        intake_id=message.intake_id,
        actor_id=message.actor_id,
        created_at=message.created_at,
    )


def message_list_to_response(
    page: MessageListPage, next_cursor: str | None
) -> MessageListResponse:
    return MessageListResponse(
        messages=[message_to_response(m) for m in page.messages],
        next_cursor=next_cursor,
    )


def webhook_ack(result: MessageWriteResult) -> InboundWebhookAck:
    return InboundWebhookAck(
        status="received",
        message_id=result.message_id,
        intake_id=result.intake_id,
    )


__all__ = [
    "InboundWebhookAck",
    "MessageListResponse",
    "MessageResponse",
    "SendMessageRequest",
    "message_list_to_response",
    "message_to_response",
    "webhook_ack",
]
