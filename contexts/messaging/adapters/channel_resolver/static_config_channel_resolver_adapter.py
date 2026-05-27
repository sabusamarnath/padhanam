"""StaticConfigChannelResolverAdapter — Phase 2-A ChannelResolver (D144, S53).

The Phase 2-A static-configuration adapter for the ``ChannelResolver``
port. Reads the operator-default channel plus operator-default address
from MessagingSettings and returns a ChannelDestination carrying those
values regardless of the (tenant_id, user_id, message_intent) inputs.

D136 Primitive 2 commits "Phase 2-A: implicit single-channel routing
(always WhatsApp; no preference structure)." The adapter honours that
commitment exactly: no user-scoped lookup, no per-intent routing
logic, no per-tenant override. Second-channel activation introduces a
new ``UserScopedChannelResolverAdapter`` at composition root; the
Protocol stays unchanged.

The adapter does NOT couple to Pydantic Settings types: it accepts the
two configuration values plainly so tests can construct the adapter
without a full MessagingSettings instance. The composition root reads
MessagingSettings once at startup and passes the resolved channel +
address.
"""

from __future__ import annotations

from uuid import UUID

from contexts.messaging.domain.channel_destination import ChannelDestination
from contexts.messaging.domain.channel_type import ChannelType
from shared_kernel.message_intent import MessageIntent


class StaticConfigChannelResolverAdapter:
    """Return the configured operator-default ChannelDestination regardless of input."""

    def __init__(
        self,
        *,
        operator_default_channel: ChannelType,
        operator_default_address: str,
    ) -> None:
        self._channel = operator_default_channel
        self._address = operator_default_address

    async def resolve_channel(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        message_intent: MessageIntent,
    ) -> ChannelDestination:
        """Return the configured ChannelDestination.

        Inputs ignored per D136 Primitive 2 Phase 2-A static-config
        commitment. The kwargs are still in the Protocol signature so
        the second-channel activation swap (a new
        UserScopedChannelResolverAdapter) is a no-call-site-change
        adapter swap.
        """
        return ChannelDestination(
            channel_type=self._channel,
            channel_address=self._address,
        )


__all__ = ["StaticConfigChannelResolverAdapter"]
