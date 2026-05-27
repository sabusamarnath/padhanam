"""Unit tests for the messaging domain layer (D129)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.messaging.domain import (
    Message,
    MessageChannel,
    MessageDirection,
    MessageStatus,
)


def _message(
    *,
    direction: MessageDirection = MessageDirection.OUTBOUND,
    status: MessageStatus = MessageStatus.QUEUED,
    jurisdiction: str = "eu-west",
    body: str = "ship the messaging substrate",
    from_address: str = "+14155238886",
    to_address: str = "+447700900123",
    actor_id: str = "cli-operator",
    external_id: str | None = None,
    intake_id=None,
    cell_payload: dict | None = None,
) -> Message:
    return Message(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction=jurisdiction,
        direction=direction,
        channel=MessageChannel.WHATSAPP,
        body=body,
        from_address=from_address,
        to_address=to_address,
        status=status,
        actor_id=actor_id,
        created_at=datetime.now(timezone.utc),
        external_id=external_id,
        intake_id=intake_id,
        cell_payload=cell_payload,
    )


def test_outbound_message_constructs() -> None:
    message = _message(direction=MessageDirection.OUTBOUND)
    assert message.direction is MessageDirection.OUTBOUND
    assert message.channel is MessageChannel.WHATSAPP
    assert message.intake_id is None
    assert message.external_id is None


def test_inbound_message_carries_intake_id() -> None:
    intake_id = uuid4()
    message = _message(
        direction=MessageDirection.INBOUND,
        status=MessageStatus.RECEIVED,
        intake_id=intake_id,
    )
    assert message.direction is MessageDirection.INBOUND
    assert message.intake_id == intake_id


def test_inbound_message_without_intake_id_is_allowed() -> None:
    # intake_id is nullable at the domain layer; the orchestration
    # populates it, but a Message may be constructed without one.
    message = _message(
        direction=MessageDirection.INBOUND, status=MessageStatus.RECEIVED
    )
    assert message.intake_id is None


def test_outbound_message_rejects_intake_id() -> None:
    with pytest.raises(ValueError, match="intake_id must be None"):
        _message(direction=MessageDirection.OUTBOUND, intake_id=uuid4())


def test_external_id_round_trips() -> None:
    message = _message(external_id="SM0123456789abcdef")
    assert message.external_id == "SM0123456789abcdef"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("jurisdiction", ""),
        ("jurisdiction", "   "),
        ("body", ""),
        ("body", "   "),
        ("from_address", ""),
        ("to_address", ""),
        ("actor_id", ""),
    ],
)
def test_non_empty_invariants(field: str, value: str) -> None:
    with pytest.raises(ValueError, match=f"Message.{field}"):
        _message(**{field: value})


def test_message_is_frozen() -> None:
    message = _message()
    with pytest.raises(FrozenInstanceError):
        message.status = MessageStatus.SENT  # type: ignore[misc]


def test_outbound_message_carries_cell_payload() -> None:
    payload = {"current_focus_artefact": {"artefact_id": str(uuid4()), "artefact_type": "case"}}
    message = _message(
        direction=MessageDirection.OUTBOUND, cell_payload=payload
    )
    assert message.cell_payload == payload


def test_inbound_message_rejects_cell_payload() -> None:
    with pytest.raises(ValueError, match="cell_payload must be None"):
        _message(
            direction=MessageDirection.INBOUND,
            status=MessageStatus.RECEIVED,
            cell_payload={"any": "value"},
        )


def test_outbound_message_with_null_cell_payload_constructs() -> None:
    message = _message(direction=MessageDirection.OUTBOUND, cell_payload=None)
    assert message.cell_payload is None


def test_enum_values_are_stable() -> None:
    assert MessageDirection.INBOUND.value == "INBOUND"
    assert MessageDirection.OUTBOUND.value == "OUTBOUND"
    assert MessageChannel.WHATSAPP.value == "WHATSAPP"
    assert {s.value for s in MessageStatus} == {
        "QUEUED",
        "SENT",
        "DELIVERED",
        "FAILED",
        "RECEIVED",
    }
