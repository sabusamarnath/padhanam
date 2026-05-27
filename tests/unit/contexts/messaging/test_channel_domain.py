"""Unit tests for ChannelType + ChannelDestination + MessageIntent value objects (D144, S53).

The Phase 2-A discriminator enum (ChannelType), the resolved
destination value object (ChannelDestination), and the cross-cutting
message-intent discriminator (MessageIntent at shared_kernel).
"""

from __future__ import annotations

import pytest

from contexts.messaging.domain.channel_destination import ChannelDestination
from contexts.messaging.domain.channel_type import ChannelType
from shared_kernel.message_intent import MessageIntent


# --------------------------------------------------------------------------- ChannelType


def test_channel_type_phase_2a_value_set() -> None:
    """Phase 2-A registers WHATSAPP only. SLACK, EMAIL, future
    channels defer to second-channel activation per D136 Primitive 1."""
    assert ChannelType.WHATSAPP.value == "whatsapp"
    assert list(ChannelType) == [ChannelType.WHATSAPP]


# --------------------------------------------------------------------------- ChannelDestination


def test_channel_destination_constructs_with_required_fields() -> None:
    destination = ChannelDestination(
        channel_type=ChannelType.WHATSAPP,
        channel_address="+15551234567",
    )
    assert destination.channel_type is ChannelType.WHATSAPP
    assert destination.channel_address == "+15551234567"


def test_channel_destination_is_frozen() -> None:
    """ChannelDestination is a frozen dataclass — direct mutation fails."""
    destination = ChannelDestination(
        channel_type=ChannelType.WHATSAPP,
        channel_address="+15551234567",
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        destination.channel_address = "+15559999999"  # type: ignore[misc]


def test_channel_destination_equality() -> None:
    """Two ChannelDestinations carrying the same fields compare equal."""
    a = ChannelDestination(
        channel_type=ChannelType.WHATSAPP,
        channel_address="+15551234567",
    )
    b = ChannelDestination(
        channel_type=ChannelType.WHATSAPP,
        channel_address="+15551234567",
    )
    assert a == b


# --------------------------------------------------------------------------- MessageIntent


def test_message_intent_phase_2a_value_set() -> None:
    """Phase 2-A registers three values. Future intents extend
    additively as new outbound surfaces land."""
    assert MessageIntent.BROADCAST_DAILY_BRIEFING.value == "broadcast_daily_briefing"
    assert (
        MessageIntent.BROADCAST_THRESHOLD_BRIEFING.value
        == "broadcast_threshold_briefing"
    )
    assert MessageIntent.REACTIVE_RESPONSE.value == "reactive_response"
    assert len(list(MessageIntent)) == 3
