"""Unit tests for the inbound-message orchestration (D128, D129, S45).

``record_intake_and_record_inbound_message`` is the fourth
intake-canonical orchestration and the first whose downstream
context is messaging rather than portfolio. The MessageWriter
consumer port is faked here; the wiring adapter is exercised by the
HTTP integration tests and the live-stack smoke.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.intake.application.ports.message_writer import (
    MessageWriteResult,
)
from contexts.intake.application.record_intake_and_record_inbound_message import (  # noqa: E501
    record_intake_and_record_inbound_message,
)
from contexts.intake.domain import IntakeSource
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import (
    INTAKE_RECORD_CREATE,
    MESSAGING_MESSAGE_RECEIVE,
    ROLE_OPERATOR,
    AuthorisationDenied,
    authorisations_for_roles,
)

from tests.unit.contexts.intake.application._fakes import (
    FakeAuditPort,
    FakeIntakeRepository,
)


class FakeMessageWriter:
    """In-memory MessageWriter consumer-port double."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.fail: bool = False

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
        if self.fail:
            raise RuntimeError("downstream messaging write failed")
        self.calls.append(
            {
                "channel": channel,
                "from_address": from_address,
                "to_address": to_address,
                "body": body,
                "external_id": external_id,
                "intake_id": intake_id,
            }
        )
        return MessageWriteResult(
            message_id=uuid4(),
            direction="INBOUND",
            channel=channel,
            body=body,
            from_address=from_address,
            to_address=to_address,
            status="RECEIVED",
            external_id=external_id,
            intake_id=intake_id,
            created_at=datetime.now(timezone.utc),
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
        actor_id="webhook-operator",
        role_list=frozenset({ROLE_OPERATOR}),
        authorisation_set=granted,
    )


def _run(
    *,
    intake_repository: FakeIntakeRepository,
    audit_port: FakeAuditPort,
    message_writer: FakeMessageWriter,
    actor: ActorContext,
    body: str = "status: Acme deal moved to legal review",
) -> MessageWriteResult:
    return asyncio.run(
        record_intake_and_record_inbound_message(
            intake_repository=intake_repository,
            audit_port=audit_port,
            message_writer=message_writer,
            actor=actor,
            channel="WHATSAPP",
            from_address="+447700900123",
            to_address="+14155238886",
            body=body,
            external_id="SMinbound01",
        )
    )


def test_orchestration_records_intake_then_writes_message() -> None:
    intake_repo = FakeIntakeRepository()
    audit = FakeAuditPort()
    writer = FakeMessageWriter()

    result = _run(
        intake_repository=intake_repo,
        audit_port=audit,
        message_writer=writer,
        actor=_actor(),
    )

    # one IntakeRecord recorded, with the WHATSAPP_INBOUND source
    assert len(intake_repo.intakes) == 1
    intake = next(iter(intake_repo.intakes.values()))
    assert intake.intake_source is IntakeSource.WHATSAPP_INBOUND
    # the intake write emitted an audit event
    assert len(audit.events) == 1
    # the message write traces to that intake
    assert len(writer.calls) == 1
    assert writer.calls[0]["intake_id"] == intake.id
    assert result.intake_id == intake.id
    assert result.direction == "INBOUND"
    assert result.status == "RECEIVED"


def test_orchestration_intake_payload_carries_message_body() -> None:
    intake_repo = FakeIntakeRepository()
    _run(
        intake_repository=intake_repo,
        audit_port=FakeAuditPort(),
        message_writer=FakeMessageWriter(),
        actor=_actor(),
        body="my 4pm with Priya slipped to Thursday",
    )
    intake = next(iter(intake_repo.intakes.values()))
    assert intake.payload.raw_text == "my 4pm with Priya slipped to Thursday"


def test_orchestration_denied_without_intake_permission() -> None:
    granted = authorisations_for_roles(
        frozenset({ROLE_OPERATOR})
    ) - {INTAKE_RECORD_CREATE}
    with pytest.raises(AuthorisationDenied, match="intake.record.create"):
        _run(
            intake_repository=FakeIntakeRepository(),
            audit_port=FakeAuditPort(),
            message_writer=FakeMessageWriter(),
            actor=_actor(authorisation_set=frozenset(granted)),
        )


def test_orchestration_denied_without_messaging_permission() -> None:
    granted = authorisations_for_roles(
        frozenset({ROLE_OPERATOR})
    ) - {MESSAGING_MESSAGE_RECEIVE}
    with pytest.raises(
        AuthorisationDenied, match="messaging.message.receive"
    ):
        _run(
            intake_repository=FakeIntakeRepository(),
            audit_port=FakeAuditPort(),
            message_writer=FakeMessageWriter(),
            actor=_actor(authorisation_set=frozenset(granted)),
        )


def test_orchestration_orphaned_intake_on_downstream_failure() -> None:
    # D128 transaction semantics: the IntakeRecord writes first; a
    # downstream messaging failure leaves it as the canonical
    # record-of-attempt rather than erasing the audit trail.
    intake_repo = FakeIntakeRepository()
    audit = FakeAuditPort()
    writer = FakeMessageWriter()
    writer.fail = True

    with pytest.raises(RuntimeError, match="downstream messaging write"):
        _run(
            intake_repository=intake_repo,
            audit_port=audit,
            message_writer=writer,
            actor=_actor(),
        )

    # the intake persisted despite the downstream failure
    assert len(intake_repo.intakes) == 1
    assert len(audit.events) == 1
