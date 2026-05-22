"""LocalEcho message delivery adapter (D129).

The local-first ``MessageDeliveryPort`` implementation. It takes no
vendor dependency and needs no credentials: an outbound send is
logged to the standard logger and a synthesised ``DeliveryResult``
(status DELIVERED, a ``local-echo-`` external id) is returned. The
audit trail of the send is unaffected — the ``send_message`` use
case emits the audit event regardless of which delivery adapter is
selected, so the LocalEcho path still lands in the audit chain.

LocalEcho is the default ``MESSAGING_ADAPTER`` for development per
D129 and the local-first principle: the full messaging substrate
runs on the laptop without a Twilio account. Production swaps to
the Twilio adapter through configuration, never a domain change.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from contexts.messaging.domain import MessageChannel, MessageStatus
from contexts.messaging.ports.message_delivery_port import DeliveryResult

_logger = logging.getLogger("padhanam.messaging.local_echo")


class LocalEchoMessageDeliveryAdapter:
    """``MessageDeliveryPort`` implementation for local-first development."""

    async def send(
        self,
        *,
        channel: MessageChannel,
        from_address: str,
        to_address: str,
        body: str,
    ) -> DeliveryResult:
        external_id = f"local-echo-{uuid4()}"
        _logger.info(
            "LocalEcho delivery: channel=%s from=%s to=%s "
            "external_id=%s body=%r",
            channel.value,
            from_address,
            to_address,
            external_id,
            body,
        )
        return DeliveryResult(
            external_id=external_id, status=MessageStatus.DELIVERED
        )


__all__ = ["LocalEchoMessageDeliveryAdapter"]
