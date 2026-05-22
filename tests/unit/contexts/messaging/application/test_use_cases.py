"""Unit tests for the messaging application layer (D128, D129)."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from contexts.messaging.application.audit_events import (
    ACTION_MESSAGE_RECEIVE,
    ACTION_MESSAGE_SEND,
)
from contexts.messaging.application.get_message import get_message
from contexts.messaging.application.list_messages import list_messages
from contexts.messaging.application.record_inbound_message import (
    record_inbound_message,
)
from contexts.messaging.application.send_message import send_message
from contexts.messaging.domain import (
    MessageChannel,
    MessageDirection,
    MessageStatus,
)
from contexts.messaging.domain.query_filters import MessageListFilters
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import (
    ROLE_OPERATOR,
    AuthorisationDenied,
    authorisations_for_roles,
)

from tests.unit.contexts.messaging.application._fakes import (
    FakeAuditPort,
    FakeMessageDeliveryPort,
    FakeMessageRepository,
)


def _actor(*, authorisation_set: frozenset[str] | None = None) -> ActorContext:
    tenant_context = TenantContext(
        tenant_id=str(uuid4()),
        jurisdiction="eu-west",
        cost_attribution_id="cost-id",
    )
    granted = (
        authorisation_set
        if authorisation_set is not None
        else authorisations_for_roles(frozenset({ROLE_OPERATOR}))
    )
    return ActorContext(
        tenant_context=tenant_context,
        actor_id="cli-operator",
        role_list=frozenset({ROLE_OPERATOR}),
        authorisation_set=granted,
    )


# --- send_message ---


def test_send_message_delivers_persists_and_audits() -> None:
    repo = FakeMessageRepository()
    delivery = FakeMessageDeliveryPort(
        status=MessageStatus.SENT, external_id="SM999"
    )
    audit = FakeAuditPort()
    actor = _actor()

    message = asyncio.run(
        send_message(
            repository=repo,
            delivery_port=delivery,
            audit_port=audit,
            actor=actor,
            from_address="+14155238886",
            to_address="+447700900123",
            body="your 3pm moved",
        )
    )

    assert message.direction is MessageDirection.OUTBOUND
    assert message.channel is MessageChannel.WHATSAPP
    assert message.status is MessageStatus.SENT
    assert message.external_id == "SM999"
    assert message.intake_id is None
    assert message.actor_id == "cli-operator"
    assert repo.messages[message.id] is message
    assert delivery.send_calls[0]["to_address"] == "+447700900123"
    assert len(audit.events) == 1
    assert audit.events[0].action_verb == ACTION_MESSAGE_SEND
    assert audit.events[0].resource_id == str(message.id)


def test_send_message_persists_failed_delivery_honestly() -> None:
    repo = FakeMessageRepository()
    delivery = FakeMessageDeliveryPort(
        status=MessageStatus.FAILED, external_id=None
    )
    message = asyncio.run(
        send_message(
            repository=repo,
            delivery_port=delivery,
            audit_port=FakeAuditPort(),
            actor=_actor(),
            from_address="+14155238886",
            to_address="+447700900123",
            body="undeliverable",
        )
    )
    assert message.status is MessageStatus.FAILED
    assert message.external_id is None
    assert message.id in repo.messages


def test_send_message_denied_without_permission() -> None:
    with pytest.raises(AuthorisationDenied, match="messaging.message.send"):
        asyncio.run(
            send_message(
                repository=FakeMessageRepository(),
                delivery_port=FakeMessageDeliveryPort(),
                audit_port=FakeAuditPort(),
                actor=_actor(authorisation_set=frozenset()),
                from_address="+1",
                to_address="+2",
                body="x",
            )
        )


# --- record_inbound_message ---


def test_record_inbound_message_persists_and_audits() -> None:
    repo = FakeMessageRepository()
    audit = FakeAuditPort()
    intake_id = uuid4()

    message = asyncio.run(
        record_inbound_message(
            repository=repo,
            audit_port=audit,
            actor=_actor(),
            from_address="+447700900123",
            to_address="+14155238886",
            body="status: Acme deal moved to legal review",
            intake_id=intake_id,
            external_id="SMinbound01",
        )
    )

    assert message.direction is MessageDirection.INBOUND
    assert message.status is MessageStatus.RECEIVED
    assert message.intake_id == intake_id
    assert message.external_id == "SMinbound01"
    assert repo.messages[message.id] is message
    assert len(audit.events) == 1
    assert audit.events[0].action_verb == ACTION_MESSAGE_RECEIVE


def test_record_inbound_message_denied_without_permission() -> None:
    with pytest.raises(
        AuthorisationDenied, match="messaging.message.receive"
    ):
        asyncio.run(
            record_inbound_message(
                repository=FakeMessageRepository(),
                audit_port=FakeAuditPort(),
                actor=_actor(authorisation_set=frozenset()),
                from_address="+1",
                to_address="+2",
                body="x",
                intake_id=uuid4(),
            )
        )


# --- get_message ---


def test_get_message_returns_persisted_message() -> None:
    repo = FakeMessageRepository()
    audit = FakeAuditPort()
    actor = _actor()
    sent = asyncio.run(
        send_message(
            repository=repo,
            delivery_port=FakeMessageDeliveryPort(),
            audit_port=audit,
            actor=actor,
            from_address="+1",
            to_address="+2",
            body="hello",
        )
    )
    fetched = asyncio.run(
        get_message(repository=repo, actor=actor, message_id=sent.id)
    )
    assert fetched is not None
    assert fetched.id == sent.id


def test_get_message_absent_returns_none() -> None:
    fetched = asyncio.run(
        get_message(
            repository=FakeMessageRepository(),
            actor=_actor(),
            message_id=uuid4(),
        )
    )
    assert fetched is None


def test_get_message_denied_without_permission() -> None:
    with pytest.raises(AuthorisationDenied, match="messaging.message.get"):
        asyncio.run(
            get_message(
                repository=FakeMessageRepository(),
                actor=_actor(authorisation_set=frozenset()),
                message_id=uuid4(),
            )
        )


# --- list_messages ---


def test_list_messages_returns_page_with_filter() -> None:
    repo = FakeMessageRepository()
    audit = FakeAuditPort()
    actor = _actor()
    asyncio.run(
        send_message(
            repository=repo,
            delivery_port=FakeMessageDeliveryPort(),
            audit_port=audit,
            actor=actor,
            from_address="+1",
            to_address="+2",
            body="outbound one",
        )
    )
    asyncio.run(
        record_inbound_message(
            repository=repo,
            audit_port=audit,
            actor=actor,
            from_address="+2",
            to_address="+1",
            body="inbound one",
            intake_id=uuid4(),
        )
    )
    page = asyncio.run(
        list_messages(
            repository=repo,
            actor=actor,
            filters=MessageListFilters(
                directions=(MessageDirection.INBOUND,)
            ),
        )
    )
    assert len(page.messages) == 1
    assert page.messages[0].direction is MessageDirection.INBOUND


def test_list_messages_denied_without_permission() -> None:
    with pytest.raises(AuthorisationDenied, match="messaging.message.list"):
        asyncio.run(
            list_messages(
                repository=FakeMessageRepository(),
                actor=_actor(authorisation_set=frozenset()),
            )
        )
