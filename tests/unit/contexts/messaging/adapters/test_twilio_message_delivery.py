"""Unit tests for the Twilio message delivery adapter (D119, D129).

The Twilio SDK Client is injected as a fake so these tests exercise
the adapter without a live Twilio account. The signature-verification
tests use the real ``RequestValidator`` — Twilio's HMAC-SHA1 webhook
signing is deterministic, so a valid signature can be computed and
verified offline.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from twilio.request_validator import RequestValidator

from contexts.messaging.adapters.outbound.twilio.twilio_message_delivery import (  # noqa: E501
    TwilioMessageDeliveryAdapter,
    channel_address,
    strip_channel_prefix,
    verify_twilio_signature,
)
from contexts.messaging.domain import MessageChannel, MessageStatus


class _FakeMessages:
    def __init__(self, sid: str, status: str) -> None:
        self._sid = sid
        self._status = status
        self.create_calls: list[dict[str, str]] = []

    def create(self, *, from_: str, to: str, body: str) -> SimpleNamespace:
        self.create_calls.append({"from_": from_, "to": to, "body": body})
        return SimpleNamespace(sid=self._sid, status=self._status)


class _FakeClient:
    def __init__(self, *, sid: str = "SMfake", status: str = "queued") -> None:
        self.messages = _FakeMessages(sid, status)


def _adapter(**kw: str) -> TwilioMessageDeliveryAdapter:
    return TwilioMessageDeliveryAdapter(
        account_sid="ACtest",
        auth_token="test-token-1234",
        client=_FakeClient(**kw),  # type: ignore[arg-type]
    )


# --- channel-address helpers ---


def test_channel_address_applies_whatsapp_prefix() -> None:
    assert (
        channel_address(MessageChannel.WHATSAPP, "+14155238886")
        == "whatsapp:+14155238886"
    )


def test_channel_address_is_idempotent() -> None:
    assert (
        channel_address(MessageChannel.WHATSAPP, "whatsapp:+14155238886")
        == "whatsapp:+14155238886"
    )


def test_strip_channel_prefix_recovers_bare_address() -> None:
    assert strip_channel_prefix("whatsapp:+14155238886") == "+14155238886"
    assert strip_channel_prefix("+14155238886") == "+14155238886"


# --- outbound send ---


def test_send_returns_delivery_result_with_sid() -> None:
    fake = _FakeClient(sid="SM0123", status="queued")
    adapter = TwilioMessageDeliveryAdapter(
        account_sid="ACtest", auth_token="tok", client=fake  # type: ignore[arg-type]
    )
    result = asyncio.run(
        adapter.send(
            channel=MessageChannel.WHATSAPP,
            from_address="+14155238886",
            to_address="+447700900123",
            body="status update",
        )
    )
    assert result.external_id == "SM0123"
    assert result.status is MessageStatus.QUEUED
    call = fake.messages.create_calls[0]
    assert call["from_"] == "whatsapp:+14155238886"
    assert call["to"] == "whatsapp:+447700900123"
    assert call["body"] == "status update"


@pytest.mark.parametrize(
    ("twilio_status", "expected"),
    [
        ("queued", MessageStatus.QUEUED),
        ("sending", MessageStatus.QUEUED),
        ("sent", MessageStatus.SENT),
        ("delivered", MessageStatus.DELIVERED),
        ("undelivered", MessageStatus.FAILED),
        ("failed", MessageStatus.FAILED),
        ("an-unknown-status", MessageStatus.QUEUED),
    ],
)
def test_send_maps_twilio_status(
    twilio_status: str, expected: MessageStatus
) -> None:
    adapter = _adapter(status=twilio_status)
    result = asyncio.run(
        adapter.send(
            channel=MessageChannel.WHATSAPP,
            from_address="+1",
            to_address="+2",
            body="x",
        )
    )
    assert result.status is expected


# --- webhook signature verification ---


def test_verify_twilio_signature_accepts_valid() -> None:
    token = "test-token-1234"
    url = "https://padhanam.test/api/v1/messaging/inbound"
    params = {
        "From": "whatsapp:+14155238886",
        "Body": "status update",
        "MessageSid": "SM0001",
    }
    signature = RequestValidator(token).compute_signature(url, params)
    assert (
        verify_twilio_signature(
            auth_token=token, url=url, params=params, signature=signature
        )
        is True
    )


def test_verify_twilio_signature_rejects_garbage_signature() -> None:
    token = "test-token-1234"
    url = "https://padhanam.test/api/v1/messaging/inbound"
    params = {"From": "whatsapp:+14155238886", "Body": "status update"}
    assert (
        verify_twilio_signature(
            auth_token=token,
            url=url,
            params=params,
            signature="not-a-real-signature",
        )
        is False
    )


def test_verify_twilio_signature_rejects_tampered_payload() -> None:
    token = "test-token-1234"
    url = "https://padhanam.test/api/v1/messaging/inbound"
    original = {"From": "whatsapp:+14155238886", "Body": "original text"}
    signature = RequestValidator(token).compute_signature(url, original)
    tampered = {"From": "whatsapp:+14155238886", "Body": "tampered text"}
    assert (
        verify_twilio_signature(
            auth_token=token,
            url=url,
            params=tampered,
            signature=signature,
        )
        is False
    )
