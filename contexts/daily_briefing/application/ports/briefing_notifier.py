"""BriefingNotifier consumer port — the outbound send surface (D146, S54).

The daily-briefing implementer's cross-context send surface. Per
D16/D17/D28 the implementer cannot import ``contexts.messaging.application``
directly (the cross-context-independent-application contract forbids
it), so it consumes this consumer-defined Protocol; the wiring adapter
at ``apps/api/_daily_briefing_wiring.py`` implements it by consulting
the ChannelResolver (D144) for the operator's channel destination and
invoking the messaging ``send_message`` use case with
``message_intent=BROADCAST_DAILY_BRIEFING``.

The notifier owns channel resolution plus delivery plus persistence
plus the outbound audit event (all inside send_message); the
implementer hands it the already-rendered channel body. The rendered
body is channel-agnostic content the messaging delivery adapter places
on the wire per the D135 domain-decides-content channel-decides-format
pattern.

Framework-free per D16 — stdlib plus shared_kernel only.
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel import ActorContext


class BriefingNotifier(Protocol):
    """Outbound send surface for the daily-briefing implementer (D146)."""

    async def send_briefing(self, *, actor: ActorContext, body: str) -> None:
        """Deliver the rendered briefing body to the operator's channel.

        The implementation resolves the operator's channel destination
        via the ChannelResolver (D144; identity-routes to WhatsApp at
        Phase 2-A) and invokes the messaging send_message use case
        (which delivers, persists the outbound Message, and emits the
        outbound audit event).
        """
        ...


__all__ = ["BriefingNotifier"]
