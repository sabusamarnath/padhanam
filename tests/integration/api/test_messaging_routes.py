"""Integration tests for the messaging HTTP routes (D129, S45).

Exercises the four routes via TestClient over an in-memory
composition: the outbound send, the GET single and list surfaces,
and the Twilio WhatsApp webhook receiver with both a valid and an
invalid X-Twilio-Signature. The webhook's signature is computed
offline with the real Twilio RequestValidator.

Tenant isolation is the adapter contract's concern and is exercised
by tests/contract/tenant_isolation/test_messaging_isolation.py
against real per-tenant databases; these route-level tests use
in-memory fakes.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from apps.api._auth_errors import register_auth_error_handlers
from apps.api._messaging_errors import register_messaging_error_handlers
from apps.api._messaging_wiring import MessagingComposition
from apps.api.middleware import get_actor_context
from apps.api.routers import messaging as messaging_router
from contexts.intake.application.ports.message_writer import MessageWriteResult
from contexts.messaging.application.record_inbound_message import (
    record_inbound_message,
)
from contexts.messaging.domain import MessageChannel
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import (
    MESSAGING_MESSAGE_SEND,
    ROLE_OPERATOR,
    authorisations_for_roles,
)
from tests.unit.contexts.intake.application._fakes import FakeIntakeRepository
from tests.unit.contexts.messaging.application._fakes import (
    FakeAuditPort,
    FakeMessageDeliveryPort,
    FakeMessageRepository,
)

_TENANT_ID = "00000000-0000-4000-8000-00000000a001"
_AUTH_TOKEN = "test-twilio-auth-token-1234"
_WEBHOOK_PATH = "/api/v1/messaging/inbound"


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_ID,
    )


def _actor(*, full: bool = True) -> ActorContext:
    role_list = frozenset({ROLE_OPERATOR})
    granted = authorisations_for_roles(role_list)
    if not full:
        granted = frozenset(granted - {MESSAGING_MESSAGE_SEND})
    return ActorContext(
        tenant_context=_ctx(),
        actor_id="operator",
        role_list=role_list,
        authorisation_set=granted,
    )


class _NoopSecurityEvents:
    def emit(self, event: object) -> None:
        pass


class _RecordingMessageWriter:
    """A MessageWriter port double that runs the real inbound use case.

    Mirrors the production MessageWriterAdapter but against the
    in-memory FakeMessageRepository, so the webhook test verifies the
    full route -> orchestration -> record_inbound_message -> repository
    path and can then GET the persisted Message.
    """

    def __init__(
        self, repository: FakeMessageRepository, audit_port: FakeAuditPort
    ) -> None:
        self._repository = repository
        self._audit_port = audit_port

    async def record_inbound_message(
        self,
        *,
        actor: ActorContext,
        channel: str,
        from_address: str,
        to_address: str,
        body: str,
        external_id: str | None,
        intake_id: UUID,
    ) -> MessageWriteResult:
        message = await record_inbound_message(
            repository=self._repository,
            audit_port=self._audit_port,
            actor=actor,
            channel=MessageChannel(channel),
            from_address=from_address,
            to_address=to_address,
            body=body,
            external_id=external_id,
            intake_id=intake_id,
        )
        return MessageWriteResult(
            message_id=message.id,
            direction=message.direction.value,
            channel=message.channel.value,
            body=message.body,
            from_address=message.from_address,
            to_address=message.to_address,
            status=message.status.value,
            external_id=message.external_id,
            intake_id=intake_id,
            created_at=message.created_at,
        )


def _build(*, full_permissions: bool = True):
    """Build a test client plus the in-memory fakes behind it."""
    message_repo = FakeMessageRepository()
    delivery = FakeMessageDeliveryPort()
    audit = FakeAuditPort()
    intake_repo = FakeIntakeRepository()
    composition = MessagingComposition(
        repository=message_repo,
        delivery_port=delivery,
        message_writer=_RecordingMessageWriter(message_repo, audit),
        from_address="+14155238886",
        webhook_tenant_id=_TENANT_ID,
        webhook_jurisdiction="eu-west",
        webhook_url="",
        twilio_auth_token=_AUTH_TOKEN,
    )
    app = FastAPI()
    register_auth_error_handlers(app)
    register_messaging_error_handlers(app)
    app.include_router(messaging_router.router)
    app.state.messaging = composition
    app.state.audit_port = audit
    app.state.intake_repository = intake_repo
    app.state.security_events = _NoopSecurityEvents()
    app.dependency_overrides[get_actor_context] = lambda: _actor(
        full=full_permissions
    )
    client = TestClient(app)
    return client, message_repo, delivery, audit, intake_repo


# --- outbound send ---


def test_send_message_route_delivers_and_persists() -> None:
    client, message_repo, delivery, _audit, _intake = _build()
    resp = client.post(
        "/api/v1/messaging/send",
        json={"to_address": "+447700900123", "body": "your 3pm moved"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["direction"] == "OUTBOUND"
    assert body["channel"] == "WHATSAPP"
    assert body["to_address"] == "+447700900123"
    assert len(delivery.send_calls) == 1
    assert len(message_repo.messages) == 1


def test_send_message_route_denied_without_permission() -> None:
    client, _repo, _delivery, _audit, _intake = _build(
        full_permissions=False
    )
    resp = client.post(
        "/api/v1/messaging/send",
        json={"to_address": "+447700900123", "body": "blocked"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "authorisation_denied"


# --- GET single and list ---


def test_get_message_route_round_trip() -> None:
    client, _repo, _delivery, _audit, _intake = _build()
    sent = client.post(
        "/api/v1/messaging/send",
        json={"to_address": "+447700900123", "body": "hello"},
    ).json()
    fetched = client.get(f"/api/v1/messaging/messages/{sent['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == sent["id"]


def test_get_message_route_absent_returns_404() -> None:
    client, _repo, _delivery, _audit, _intake = _build()
    resp = client.get(f"/api/v1/messaging/messages/{uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "message_not_found"


def test_list_messages_route_returns_sent_messages() -> None:
    client, _repo, _delivery, _audit, _intake = _build()
    client.post(
        "/api/v1/messaging/send",
        json={"to_address": "+447700900123", "body": "one"},
    )
    resp = client.get("/api/v1/messaging/messages")
    assert resp.status_code == 200
    assert len(resp.json()["messages"]) == 1


# --- inbound webhook ---


def _inbound_form() -> dict[str, str]:
    return {
        "From": "whatsapp:+447700900123",
        "To": "whatsapp:+14155238886",
        "Body": "status: Acme deal moved to legal review",
        "MessageSid": "SMinbound0001",
    }


def test_inbound_webhook_valid_signature_records_intake_and_message() -> None:
    client, message_repo, _delivery, _audit, intake_repo = _build()
    form = _inbound_form()
    url = f"http://testserver{_WEBHOOK_PATH}"
    signature = RequestValidator(_AUTH_TOKEN).compute_signature(url, form)

    resp = client.post(
        _WEBHOOK_PATH,
        data=form,
        headers={"X-Twilio-Signature": signature},
    )
    assert resp.status_code == 200
    ack = resp.json()
    assert ack["status"] == "received"
    # the inbound message landed as both an IntakeRecord and a Message
    assert len(intake_repo.intakes) == 1
    assert len(message_repo.messages) == 1
    message = next(iter(message_repo.messages.values()))
    assert message.direction.value == "INBOUND"
    assert str(message.id) == ack["message_id"]
    assert str(message.intake_id) == ack["intake_id"]


def test_inbound_webhook_invalid_signature_rejected() -> None:
    client, message_repo, _delivery, _audit, intake_repo = _build()
    resp = client.post(
        _WEBHOOK_PATH,
        data=_inbound_form(),
        headers={"X-Twilio-Signature": "not-a-valid-signature"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "webhook_signature_invalid"
    # the rejected webhook wrote nothing
    assert len(intake_repo.intakes) == 0
    assert len(message_repo.messages) == 0
