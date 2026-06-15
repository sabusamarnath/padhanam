"""CheckinMessageSender consumer port (D192, D194, S97b).

The composer's outbound send boundary. The real adapter (wired in ``apps/``)
delivers via the messaging channel (Twilio at the live round-trip); tests fake
it up to this boundary so the composer's eligibility, message, and pending
creation verify without a live send.

Framework-free; stdlib-only Protocol shape.
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel import ActorContext


class CheckinMessageSender(Protocol):
    """Deliver the outbound daily check-in prompt to the operator."""

    async def send(self, *, actor: ActorContext, body: str) -> None:
        """Send the check-in prompt to the operator's configured address."""
        ...


__all__ = ["CheckinMessageSender"]
