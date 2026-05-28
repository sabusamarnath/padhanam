"""ChannelResolver consumer port — channel selection for outbound (D144, S53).

D136 Primitive 2's structural activation at Phase 2-A. The port carries
a single async method ``resolve_channel`` taking tenant_id, user_id,
and a MessageIntent discriminator; returns a ChannelDestination
carrying the channel type plus the per-channel destination address.

Two consumers at P15: BroadcastDispatch (D143) consults the resolver
before invoking the BroadcastFlow implementer; reactive outbound
(``send_message`` use case from S45) refactors to consult the
resolver before send. At Phase 2-A the static-config adapter ignores
user_id and message_intent and returns the operator-default channel
configured in MessagingSettings — identity routing for reactive
outbound that arrives from the operator's WhatsApp inbound.

The user-scoped channel preference state defers to the second-channel
activation trigger per D136 Primitive 1's User aggregate root
dependency. At activation, a new ``UserScopedChannelResolverAdapter``
swaps in at composition root; the Protocol stays unchanged; only the
adapter swaps. Forward-compatible by construction.

Ports layer is pure per D16 — stdlib only.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from contexts.messaging.domain.channel_destination import ChannelDestination
from shared_kernel.message_intent import MessageIntent


@runtime_checkable
class ChannelResolver(Protocol):
    """Resolve the outbound channel destination for a (tenant, user, intent).

    Not-yet-implemented marker (Phase 2-A; Ciborra-audit C2 correction):
    per-user and per-intent channel resolution is not yet built. The
    ``user_id`` and ``message_intent`` parameters are declared for
    forward-compatibility (D144), but no shipped adapter consumes them —
    the only Phase-2-A adapter (``StaticConfigChannelResolverAdapter``)
    returns the operator-default channel and discards these inputs
    explicitly. Until a ``UserScopedChannelResolverAdapter`` lands —
    gated on the D136 Primitive 1 User aggregate plus a second channel —
    this Protocol declares more than any adapter delivers, by design and
    disclosed here rather than silently claimed. The Protocol stays
    unchanged across that swap per D144's forward-compatibility
    commitment.
    """

    async def resolve_channel(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        message_intent: MessageIntent,
    ) -> ChannelDestination:
        """Return the ChannelDestination for the given resolution inputs."""
        ...


__all__ = ["ChannelResolver"]
