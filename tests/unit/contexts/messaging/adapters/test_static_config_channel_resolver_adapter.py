"""Unit tests for StaticConfigChannelResolverAdapter (D144, S53).

The Phase 2-A static-configuration adapter for ChannelResolver. The
adapter ignores (tenant_id, user_id, message_intent) and returns the
configured operator-default ChannelDestination — D136 Primitive 2's
Phase 2-A commitment.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from contexts.messaging.adapters.channel_resolver.static_config_channel_resolver_adapter import (
    StaticConfigChannelResolverAdapter,
)
from contexts.messaging.application.ports.channel_resolver import (
    ChannelResolver,
)
from contexts.messaging.domain.channel_destination import ChannelDestination
from contexts.messaging.domain.channel_type import ChannelType
from shared_kernel.message_intent import MessageIntent


def _resolve(
    adapter: StaticConfigChannelResolverAdapter,
    *,
    intent: MessageIntent,
) -> ChannelDestination:
    return asyncio.run(
        adapter.resolve_channel(
            tenant_id=uuid4(),
            user_id="operator-001",
            message_intent=intent,
        )
    )


def test_adapter_satisfies_channel_resolver_protocol() -> None:
    adapter = StaticConfigChannelResolverAdapter(
        operator_default_channel=ChannelType.WHATSAPP,
        operator_default_address="+15551234567",
    )
    assert isinstance(adapter, ChannelResolver)


def test_resolve_returns_configured_channel_and_address() -> None:
    adapter = StaticConfigChannelResolverAdapter(
        operator_default_channel=ChannelType.WHATSAPP,
        operator_default_address="+15551234567",
    )
    destination = _resolve(adapter, intent=MessageIntent.REACTIVE_RESPONSE)
    assert destination.channel_type is ChannelType.WHATSAPP
    assert destination.channel_address == "+15551234567"


def test_resolve_ignores_message_intent_phase_2a() -> None:
    """Per D144 Phase 2-A: the static-config adapter returns the
    operator-default regardless of MessageIntent. The kwarg is part of
    the Protocol signature so the multi-channel activation swap is
    a no-call-site-change adapter swap."""
    adapter = StaticConfigChannelResolverAdapter(
        operator_default_channel=ChannelType.WHATSAPP,
        operator_default_address="+15551234567",
    )
    for intent in MessageIntent:
        destination = _resolve(adapter, intent=intent)
        assert destination.channel_type is ChannelType.WHATSAPP
        assert destination.channel_address == "+15551234567"


def test_resolve_ignores_tenant_and_user() -> None:
    """Per D144 Phase 2-A: tenant_id and user_id pass through the kwargs
    but the static-config adapter does not consult them. Multi-tenant
    deployments at Phase 2-A all see the same operator-default."""
    adapter = StaticConfigChannelResolverAdapter(
        operator_default_channel=ChannelType.WHATSAPP,
        operator_default_address="+15551234567",
    )

    async def _drive() -> tuple[ChannelDestination, ChannelDestination]:
        first = await adapter.resolve_channel(
            tenant_id=uuid4(),
            user_id="op-a",
            message_intent=MessageIntent.BROADCAST_DAILY_BRIEFING,
        )
        second = await adapter.resolve_channel(
            tenant_id=uuid4(),
            user_id="op-b",
            message_intent=MessageIntent.BROADCAST_DAILY_BRIEFING,
        )
        return first, second

    first, second = asyncio.run(_drive())
    assert first == second


def test_per_user_per_intent_resolution_not_yet_implemented() -> None:
    """Not-yet-implemented marker (D144; Ciborra-audit C2 correction).

    Per-user / per-intent channel resolution is not built at Phase 2-A.
    Across the full cross-product of distinct users and every
    MessageIntent, the static-config adapter returns one invariant
    operator-default destination — pinning the discard as the intended,
    disclosed not-yet-implemented contract rather than an accidental
    bug. When the UserScopedChannelResolverAdapter lands it is a new
    adapter carrying its own per-user tests; this adapter's contract
    stays operator-default-only.
    """
    adapter = StaticConfigChannelResolverAdapter(
        operator_default_channel=ChannelType.WHATSAPP,
        operator_default_address="+15551234567",
    )

    async def _drive() -> set[ChannelDestination]:
        seen: set[ChannelDestination] = set()
        for user_id in ("operator-001", "operator-002", "someone-else"):
            for intent in MessageIntent:
                seen.add(
                    await adapter.resolve_channel(
                        tenant_id=uuid4(),
                        user_id=user_id,
                        message_intent=intent,
                    )
                )
        return seen

    distinct = asyncio.run(_drive())
    assert distinct == {
        ChannelDestination(
            channel_type=ChannelType.WHATSAPP,
            channel_address="+15551234567",
        )
    }


def test_resolve_returns_empty_address_when_not_configured() -> None:
    """Empty address default keeps local development without a configured
    operator-address able to construct MessagingSettings — the static-
    config adapter surfaces the empty value rather than raising. Phase
    2-A operator dogfooding configures the address at deployment time."""
    adapter = StaticConfigChannelResolverAdapter(
        operator_default_channel=ChannelType.WHATSAPP,
        operator_default_address="",
    )
    destination = _resolve(adapter, intent=MessageIntent.REACTIVE_RESPONSE)
    assert destination.channel_address == ""
