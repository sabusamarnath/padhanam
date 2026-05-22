"""Unit tests for the LocalEcho message delivery adapter (D129)."""

from __future__ import annotations

import asyncio

from contexts.messaging.adapters.outbound.local_echo.local_echo_message_delivery import (  # noqa: E501
    LocalEchoMessageDeliveryAdapter,
)
from contexts.messaging.domain import MessageChannel, MessageStatus


def _send(adapter: LocalEchoMessageDeliveryAdapter, body: str = "hello"):
    return asyncio.run(
        adapter.send(
            channel=MessageChannel.WHATSAPP,
            from_address="+14155238886",
            to_address="+447700900123",
            body=body,
        )
    )


def test_local_echo_send_returns_delivered() -> None:
    result = _send(LocalEchoMessageDeliveryAdapter())
    assert result.status is MessageStatus.DELIVERED
    assert result.external_id is not None
    assert result.external_id.startswith("local-echo-")


def test_local_echo_send_synthesises_unique_external_ids() -> None:
    adapter = LocalEchoMessageDeliveryAdapter()
    first = _send(adapter, body="first")
    second = _send(adapter, body="second")
    assert first.external_id != second.external_id
