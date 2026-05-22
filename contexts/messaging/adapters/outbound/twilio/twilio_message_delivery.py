"""Twilio Python SDK message delivery adapter (D119, D129).

Implements ``MessageDeliveryPort`` against the Twilio REST API.
WhatsApp addresses are ``whatsapp:``-prefixed for the Twilio API;
the domain stores the bare address, and this adapter applies the
prefix on send and strips it on inbound-webhook parsing.

This is the only module where ``import twilio`` resolves to a real
package — the ``twilio-confined`` import-linter contract enforces
the confinement per D27/D30. Per the scenario-driven protocol
selection principle (principles.md line 22), the direct vendor SDK
is the framing-time disposition for this service-to-service runtime
integration; the Twilio MCP server is Alpha-stage and loses to the
production-grade SDK until it reaches production-readiness.

The blocking Twilio SDK call runs off the event loop via
``asyncio.to_thread`` so an outbound send does not stall the API
process.
"""

from __future__ import annotations

import asyncio
from typing import Any

from twilio.request_validator import RequestValidator
from twilio.rest import Client

from contexts.messaging.domain import MessageChannel, MessageStatus
from contexts.messaging.ports.message_delivery_port import DeliveryResult

_WHATSAPP_PREFIX = "whatsapp:"

# Twilio reports its own message-status vocabulary; map it onto the
# domain MessageStatus. Unknown values fall back to QUEUED — the
# honest "the vendor accepted it; the lifecycle has not resolved".
_TWILIO_STATUS_MAP: dict[str, MessageStatus] = {
    "queued": MessageStatus.QUEUED,
    "accepted": MessageStatus.QUEUED,
    "scheduled": MessageStatus.QUEUED,
    "sending": MessageStatus.QUEUED,
    "sent": MessageStatus.SENT,
    "delivered": MessageStatus.DELIVERED,
    "read": MessageStatus.DELIVERED,
    "undelivered": MessageStatus.FAILED,
    "failed": MessageStatus.FAILED,
    "canceled": MessageStatus.FAILED,
}


def channel_address(channel: MessageChannel, address: str) -> str:
    """Apply a channel's vendor address prefix.

    WhatsApp addresses are ``whatsapp:``-prefixed for the Twilio
    API; the domain stores the bare address. Idempotent.
    """
    if channel is MessageChannel.WHATSAPP and not address.startswith(
        _WHATSAPP_PREFIX
    ):
        return _WHATSAPP_PREFIX + address
    return address


def strip_channel_prefix(address: str) -> str:
    """Strip a channel address prefix, recovering the bare address.

    Used by the inbound-webhook receiver: Twilio delivers WhatsApp
    addresses as ``whatsapp:+E164``; the domain Message stores the
    bare ``+E164``.
    """
    if address.startswith(_WHATSAPP_PREFIX):
        return address[len(_WHATSAPP_PREFIX) :]
    return address


def verify_twilio_signature(
    *,
    auth_token: str,
    url: str,
    params: dict[str, Any],
    signature: str,
) -> bool:
    """Verify an ``X-Twilio-Signature`` header against the request.

    Twilio signs every webhook with an HMAC-SHA1 of the full URL
    plus the sorted POST parameters, keyed on the account auth
    token. The webhook receiver invokes this before processing an
    inbound payload; a failed check rejects the request as a 403.
    """
    return RequestValidator(auth_token).validate(url, params, signature)


class TwilioMessageDeliveryAdapter:
    """``MessageDeliveryPort`` implementation backed by the Twilio SDK.

    ``client`` is injectable so unit tests exercise the adapter
    without a live Twilio account; production wiring passes the
    account SID and auth token and the adapter builds the Client.
    """

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        client: Client | None = None,
    ) -> None:
        self._client = (
            client
            if client is not None
            else Client(account_sid, auth_token)
        )

    async def send(
        self,
        *,
        channel: MessageChannel,
        from_address: str,
        to_address: str,
        body: str,
    ) -> DeliveryResult:
        created = await asyncio.to_thread(
            self._client.messages.create,
            from_=channel_address(channel, from_address),
            to=channel_address(channel, to_address),
            body=body,
        )
        status = _TWILIO_STATUS_MAP.get(
            str(created.status or "").lower(), MessageStatus.QUEUED
        )
        return DeliveryResult(external_id=created.sid, status=status)


__all__ = [
    "TwilioMessageDeliveryAdapter",
    "channel_address",
    "strip_channel_prefix",
    "verify_twilio_signature",
]
