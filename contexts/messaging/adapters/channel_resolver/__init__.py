"""ChannelResolver adapters for the messaging context (D144, S53).

Carries the static-configuration adapter at Phase 2-A. The
composition root selects an adapter; future swap to
``UserScopedChannelResolverAdapter`` at second-channel activation
keeps the call sites unchanged.
"""

from contexts.messaging.adapters.channel_resolver.static_config_channel_resolver_adapter import (
    StaticConfigChannelResolverAdapter,
)

__all__ = ["StaticConfigChannelResolverAdapter"]
