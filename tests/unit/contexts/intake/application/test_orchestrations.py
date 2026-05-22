"""Unit tests for the intake-canonical orchestration use cases (D127, D128)."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from contexts.intake.application import (
    record_intake_and_create_case,
    record_intake_and_revise_data_point,
)
from contexts.intake.domain import ManualEntryPayload
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import (
    INTAKE_RECORD_CREATE,
    PORTFOLIO_CASE_CREATE,
    PORTFOLIO_DATA_POINT_REVISE,
    ROLE_OPERATOR,
    AuthorisationDenied,
    authorisations_for_roles,
)
from tests.unit.contexts.intake.application._fakes import (
    FakeAuditPort,
    FakeIntakeRepository,
    FakePortfolioWriter,
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


def _payload() -> ManualEntryPayload:
    return ManualEntryPayload(raw_text="ship S44b", intent_hint="create-case")


def _run(coro):
    return asyncio.run(coro)


# --- record_intake_and_create_case ---------------------------------


def test_create_case_orchestration_records_intake_then_writes_case() -> None:
    intake_repo = FakeIntakeRepository()
    audit = FakeAuditPort()
    writer = FakePortfolioWriter()
    result = _run(
        record_intake_and_create_case(
            intake_repository=intake_repo,
            audit_port=audit,
            portfolio_writer=writer,
            actor=_actor(),
            payload=_payload(),
            title="Q3 board deck",
        )
    )
    # the intake recorded first
    assert len(intake_repo.intakes) == 1
    intake = next(iter(intake_repo.intakes.values()))
    # the case written, carrying the recorded intake's id
    assert len(writer.created_cases) == 1
    assert result.title == "Q3 board deck"
    assert result.intake_id == intake.id
    # one intake audit event
    assert [e.action_verb for e in audit.events] == ["intake.record.create"]


def test_create_case_orchestration_denied_without_intake_permission() -> None:
    intake_repo = FakeIntakeRepository()
    writer = FakePortfolioWriter()
    actor = _actor(
        authorisation_set=frozenset({PORTFOLIO_CASE_CREATE})
    )
    with pytest.raises(AuthorisationDenied) as excinfo:
        _run(
            record_intake_and_create_case(
                intake_repository=intake_repo, audit_port=FakeAuditPort(),
                portfolio_writer=writer, actor=actor,
                payload=_payload(), title="t",
            )
        )
    assert excinfo.value.permission == INTAKE_RECORD_CREATE
    # fail-fast: nothing written
    assert intake_repo.intakes == {}
    assert writer.created_cases == []


def test_create_case_orchestration_denied_without_portfolio_permission() -> None:
    intake_repo = FakeIntakeRepository()
    writer = FakePortfolioWriter()
    actor = _actor(
        authorisation_set=frozenset({INTAKE_RECORD_CREATE})
    )
    with pytest.raises(AuthorisationDenied) as excinfo:
        _run(
            record_intake_and_create_case(
                intake_repository=intake_repo, audit_port=FakeAuditPort(),
                portfolio_writer=writer, actor=actor,
                payload=_payload(), title="t",
            )
        )
    assert excinfo.value.permission == PORTFOLIO_CASE_CREATE
    # the orchestration's dual decorator fail-fasts before the intake write
    assert intake_repo.intakes == {}
    assert writer.created_cases == []


def test_create_case_orchestration_orphaned_intake_on_downstream_failure() -> None:
    """D128 two-transaction intake-first: a downstream Case-write
    failure leaves the IntakeRecord persisted as the record-of-attempt."""
    intake_repo = FakeIntakeRepository()
    writer = FakePortfolioWriter()
    writer.fail = True
    with pytest.raises(RuntimeError, match="downstream"):
        _run(
            record_intake_and_create_case(
                intake_repository=intake_repo, audit_port=FakeAuditPort(),
                portfolio_writer=writer, actor=_actor(),
                payload=_payload(), title="t",
            )
        )
    # the intake survives — the honest canonical record-of-attempt
    assert len(intake_repo.intakes) == 1
    assert writer.created_cases == []


# --- record_intake_and_revise_data_point ---------------------------


def test_revise_orchestration_records_intake_then_revises() -> None:
    intake_repo = FakeIntakeRepository()
    audit = FakeAuditPort()
    writer = FakePortfolioWriter()
    dp_id = uuid4()
    result = _run(
        record_intake_and_revise_data_point(
            intake_repository=intake_repo,
            audit_port=audit,
            portfolio_writer=writer,
            actor=_actor(),
            payload=_payload(),
            data_point_id=dp_id,
            value={"progress": 100},
        )
    )
    assert len(intake_repo.intakes) == 1
    intake = next(iter(intake_repo.intakes.values()))
    assert result.data_point_id == dp_id
    assert result.intake_id == intake.id
    assert result.current_value == {"progress": 100}


def test_revise_orchestration_denied_without_portfolio_permission() -> None:
    intake_repo = FakeIntakeRepository()
    writer = FakePortfolioWriter()
    actor = _actor(authorisation_set=frozenset({INTAKE_RECORD_CREATE}))
    with pytest.raises(AuthorisationDenied) as excinfo:
        _run(
            record_intake_and_revise_data_point(
                intake_repository=intake_repo, audit_port=FakeAuditPort(),
                portfolio_writer=writer, actor=actor, payload=_payload(),
                data_point_id=uuid4(), value={},
            )
        )
    assert excinfo.value.permission == PORTFOLIO_DATA_POINT_REVISE
    assert intake_repo.intakes == {}
