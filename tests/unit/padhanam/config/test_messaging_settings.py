"""Unit tests for MessagingSettings extension (D144, S53).

The Phase 2-A extension adds ``operator_default_channel`` and
``operator_default_address`` per D144. The fields default to
WhatsApp + empty-string so local development without operator
configuration constructs cleanly.
"""

from __future__ import annotations

import pytest

from contexts.messaging.domain.channel_type import ChannelType
from padhanam.config.messaging import MessagingSettings


def test_default_operator_channel_is_whatsapp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default ``operator_default_channel`` is WhatsApp per D144 / D136
    Primitive 2 Phase 2-A commitment."""
    # Strip env vars that might override.
    monkeypatch.delenv("OPERATOR_DEFAULT_CHANNEL", raising=False)
    monkeypatch.delenv("OPERATOR_DEFAULT_ADDRESS", raising=False)
    settings = MessagingSettings()
    assert settings.operator_default_channel is ChannelType.WHATSAPP


def test_default_operator_address_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default ``operator_default_address`` is empty so local development
    constructs MessagingSettings without operator configuration. The
    static-config ChannelResolver adapter surfaces the empty value."""
    monkeypatch.delenv("OPERATOR_DEFAULT_ADDRESS", raising=False)
    settings = MessagingSettings()
    assert settings.operator_default_address == ""


def test_operator_address_reads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """``OPERATOR_DEFAULT_ADDRESS`` env var populates the field via
    Pydantic Settings — Phase 2-A deployment configures the field."""
    monkeypatch.setenv("OPERATOR_DEFAULT_ADDRESS", "+15551234567")
    settings = MessagingSettings()
    assert settings.operator_default_address == "+15551234567"


def test_operator_channel_reads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """``OPERATOR_DEFAULT_CHANNEL`` env var populates the channel field."""
    monkeypatch.setenv("OPERATOR_DEFAULT_CHANNEL", "whatsapp")
    settings = MessagingSettings()
    assert settings.operator_default_channel is ChannelType.WHATSAPP
