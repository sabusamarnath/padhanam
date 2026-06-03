"""ThresholdNotifier consumer port — the outbound send surface (D146, D153, S57).

The threshold-briefing's cross-context send surface, mirroring
daily-briefing's BriefingNotifier (D146). Per D16/D17/D28 the implementer
cannot import ``contexts.messaging.application`` directly; it consumes
this consumer-defined port, and the ``apps/`` wiring adapter implements it
by resolving the operator's channel via the ChannelResolver (D144) and
invoking the messaging ``send_message`` use case with
``message_intent=BROADCAST_THRESHOLD_BRIEFING``.

Framework-free per D16 — stdlib plus shared_kernel only.
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel import ActorContext


class ThresholdNotifier(Protocol):
    """Outbound send surface for the threshold-briefing implementer (D153)."""

    async def send_briefing(self, *, actor: ActorContext, body: str) -> None:
        """Deliver the rendered threshold-briefing body to the operator's channel.

        The implementation resolves the operator's channel destination via
        the ChannelResolver (D144) and invokes the messaging send_message
        use case (delivery, persistence, outbound audit event).
        """
        ...


__all__ = ["ThresholdNotifier"]
