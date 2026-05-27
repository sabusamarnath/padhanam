"""MessageIntent enum — the channel-resolution input discriminator (D144, S53).

Carries the Phase 2-A values the ChannelResolver (D144) consults at
``resolve_channel``. The Phase 2-A static-config adapter ignores the
parameter (it returns the operator-default channel regardless); future
channel-resolution logic at multi-channel activation may use this
discriminator to route different message types to different channels
(e.g., daily briefings to email, threshold alerts to WhatsApp).

Lives at shared_kernel rather than ``contexts/messaging/`` because
BroadcastFlow implementers at P15+ (S54 onwards) construct
MessageIntent values when invoking channel resolution; placing the
enum at shared_kernel avoids cross-context coupling to messaging's
domain layer when an implementer at a non-messaging context (e.g.,
calendar-conversation at S55 referencing ``REACTIVE_RESPONSE``)
constructs the resolver input.

Framework-free per D16 — shared_kernel is policed; stdlib only.
"""

from __future__ import annotations

from enum import StrEnum


class MessageIntent(StrEnum):
    """The Phase 2-A message-intent discriminator for channel resolution.

    Three values. Future intents extend additively as new outbound
    surfaces land; the static-config ChannelResolver adapter at Phase
    2-A ignores this parameter, so extensions do not break Phase 2-A
    behaviour.
    """

    BROADCAST_DAILY_BRIEFING = "broadcast_daily_briefing"
    BROADCAST_THRESHOLD_BRIEFING = "broadcast_threshold_briefing"
    REACTIVE_RESPONSE = "reactive_response"


__all__ = ["MessageIntent"]
