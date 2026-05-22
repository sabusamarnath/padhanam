"""Outbound delivery port for the messaging context (D129).

``MessageDeliveryPort`` is the vendor-agnostic outbound-send
abstraction. The Twilio Python SDK adapter and the LocalEcho
local-first adapter both implement it; selection is configuration
(the ``MESSAGING_ADAPTER`` environment variable) per D129, never a
domain change — the vendor-flexibility principle.

``send`` is async so the adapter can run a blocking vendor SDK call
off the event loop; it returns a ``DeliveryResult`` carrying the
vendor's accepted status and message identifier, which the
``send_message`` use case stamps onto the persisted Message.

Ports layer is pure per D16 — no vendor SDKs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from contexts.messaging.domain import MessageChannel, MessageStatus


@dataclass(frozen=True)
class DeliveryResult:
    """The outcome of an outbound delivery attempt.

    ``external_id`` is the vendor's message identifier (the Twilio
    MessageSid, or a synthesised id under the LocalEcho adapter);
    ``status`` is the vendor-reported delivery status.
    """

    external_id: str | None
    status: MessageStatus


class MessageDeliveryPort(Protocol):
    """Vendor-agnostic outbound message delivery."""

    async def send(
        self,
        *,
        channel: MessageChannel,
        from_address: str,
        to_address: str,
        body: str,
    ) -> DeliveryResult:
        """Deliver an outbound message; return the vendor's result."""
        ...


__all__ = ["DeliveryResult", "MessageDeliveryPort"]
