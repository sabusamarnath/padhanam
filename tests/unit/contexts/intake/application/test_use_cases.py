"""Unit tests for the intake standalone use cases (D127, D128)."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from contexts.intake.application import get_intake, list_intakes, record_intake
from contexts.intake.domain import IntakeSource, ManualEntryPayload
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import (
    ROLE_OPERATOR,
    AuthorisationDenied,
    authorisations_for_roles,
)
from tests.unit.contexts.intake.application._fakes import (
    FakeAuditPort,
    FakeIntakeRepository,
)

_TENANT_ID = "00000000-0000-4000-8000-00000000a001"


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_ID,
    )


def _actor(*, authorisation_set: frozenset[str] | None = None) -> ActorContext:
    role_list = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=_ctx(),
        actor_id="operator",
        role_list=role_list,
        authorisation_set=(
            authorisations_for_roles(role_list)
            if authorisation_set is None
            else authorisation_set
        ),
    )


def _payload(text: str = "ship S44b") -> ManualEntryPayload:
    return ManualEntryPayload(raw_text=text)


def _run(coro):
    return asyncio.run(coro)


# --- happy paths ---------------------------------------------------


def test_record_intake_persists_and_audits() -> None:
    repo = FakeIntakeRepository()
    audit = FakeAuditPort()
    intake = _run(
        record_intake(
            repository=repo,
            audit_port=audit,
            actor=_actor(),
            intake_source=IntakeSource.MANUAL_ENTRY,
            payload=_payload(),
        )
    )
    assert intake.id in repo.intakes
    assert intake.intake_source is IntakeSource.MANUAL_ENTRY
    assert intake.authored_by.user_id == "operator"
    assert [e.action_verb for e in audit.events] == ["intake.record.create"]
    assert audit.events[0].actor == "operator"


def test_get_intake_returns_record() -> None:
    repo = FakeIntakeRepository()
    audit = FakeAuditPort()
    intake = _run(
        record_intake(
            repository=repo, audit_port=audit, actor=_actor(),
            intake_source=IntakeSource.MANUAL_ENTRY, payload=_payload(),
        )
    )
    fetched = _run(
        get_intake(repository=repo, actor=_actor(), intake_id=intake.id)
    )
    assert fetched is not None
    assert fetched.id == intake.id


def test_get_intake_unknown_returns_none() -> None:
    repo = FakeIntakeRepository()
    fetched = _run(
        get_intake(repository=repo, actor=_actor(), intake_id=uuid4())
    )
    assert fetched is None


def test_list_intakes_returns_all_seeded() -> None:
    repo = FakeIntakeRepository()
    audit = FakeAuditPort()
    for i in range(3):
        _run(
            record_intake(
                repository=repo, audit_port=audit, actor=_actor(),
                intake_source=IntakeSource.MANUAL_ENTRY,
                payload=_payload(f"intake {i}"),
            )
        )
    page = _run(
        list_intakes(repository=repo, actor=_actor(), page_size=10)
    )
    assert len(page.intakes) == 3


# --- deny paths: the use-case-boundary decorator (D126) ------------


def test_record_intake_denied_without_permission() -> None:
    repo = FakeIntakeRepository()
    audit = FakeAuditPort()
    with pytest.raises(AuthorisationDenied) as excinfo:
        _run(
            record_intake(
                repository=repo, audit_port=audit,
                actor=_actor(authorisation_set=frozenset()),
                intake_source=IntakeSource.MANUAL_ENTRY, payload=_payload(),
            )
        )
    assert excinfo.value.permission == "intake.record.create"
    assert repo.intakes == {}
    assert audit.events == []


def test_get_intake_denied_without_permission() -> None:
    repo = FakeIntakeRepository()
    with pytest.raises(AuthorisationDenied) as excinfo:
        _run(
            get_intake(
                repository=repo,
                actor=_actor(authorisation_set=frozenset()),
                intake_id=uuid4(),
            )
        )
    assert excinfo.value.permission == "intake.record.get"


def test_list_intakes_denied_without_permission() -> None:
    repo = FakeIntakeRepository()
    with pytest.raises(AuthorisationDenied) as excinfo:
        _run(
            list_intakes(
                repository=repo,
                actor=_actor(authorisation_set=frozenset()),
                page_size=10,
            )
        )
    assert excinfo.value.permission == "intake.record.list"
