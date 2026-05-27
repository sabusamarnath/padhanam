"""ChannelDestination value object — the resolved outbound destination (D144, S53).

Returned by ``ChannelResolver.resolve_channel`` (D144). Carries the
channel discriminator plus the per-channel destination identifier
(the WhatsApp phone number at Phase 2-A; future channels carry
their own per-channel address shapes).

Phase 2-A frozen dataclass with two fields. The second-channel
activation introduces no shape change — only the resolver adapter
swaps. Forward-compatible by construction.

Domain layer per D16 — stdlib only, no vendor SDK imports.
"""

from __future__ import annotations

from dataclasses import dataclass

from contexts.messaging.domain.channel_type import ChannelType


@dataclass(frozen=True)
class ChannelDestination:
    """The resolved outbound destination for a platform-initiated or
    reactive message.

    ``channel_type`` discriminates which channel adapter handles the
    send; ``channel_address`` carries the per-channel destination
    identifier (the WhatsApp E.164 phone number at Phase 2-A; future
    channels carry per-channel-shaped addresses such as Slack channel
    IDs or email addresses).
    """

    channel_type: ChannelType
    channel_address: str


__all__ = ["ChannelDestination"]
