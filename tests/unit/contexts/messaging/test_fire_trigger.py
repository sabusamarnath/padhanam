"""Unit tests for the FireTrigger use case (D145, D147, S54).

Exercises the seven-step endpoint flow across the fresh-fire path
(insert -> audit -> dispatch -> ACCEPTED) and the duplicate path
(conflict -> ALREADY_FIRED, no audit, no dispatch) with stubbed ports.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from contexts.messaging.application.fire_trigger import (
    FireTriggerStatus,
    fire_trigger,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles
from shared_kernel.broadcast_flow import BroadcastTriggerType, TriggerContext
from tests.unit.contexts.messaging.application._fakes import (
    FakeAuditPort,
    FakeFiredTriggersRepository,
)

_TENANT = "00000000-0000-4000-8000-00000000a001"


def _actor() -> ActorContext:
    role_list = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT,
            jurisdiction="eu-west",
            cost_attribution_id=_TENANT,
        ),
        actor_id="operator-001",
        role_list=role_list,
        authorisation_set=authorisations_for_roles(role_list),
    )


@dataclass
class _RecordingDispatch:
    calls: list[tuple[UUID, str, TriggerContext]] = field(default_factory=list)

    async def dispatch(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        trigger_context: TriggerContext,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.calls.append((tenant_id, user_id, trigger_context))


def _daily_context() -> TriggerContext:
    return TriggerContext(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
        trigger_id=uuid4(),
        triggered_at="2026-05-28T06:00:00+00:00",
    )


def test_fresh_fire_inserts_audits_and_dispatches() -> None:
    repo = FakeFiredTriggersRepository()
    audit = FakeAuditPort()
    dispatch = _RecordingDispatch()
    context = _daily_context()

    result = asyncio.run(
        fire_trigger(
            fired_triggers_repository=repo,
            audit_port=audit,
            broadcast_dispatch=dispatch,
            actor=_actor(),
            trigger_context=context,
            operator_timezone="UTC",
        )
    )

    assert result.status is FireTriggerStatus.ACCEPTED
    assert result.trigger_id == str(context.trigger_id)
    # idempotency row inserted
    assert len(repo.inserted) == 1
    assert repo.inserted[0][2] == "daily_scheduled"
    # one BROADCAST_INITIATED audit event emitted
    assert len(audit.events) == 1
    assert audit.events[0].action_verb == "messaging.broadcast.initiated"
    # dispatch invoked once with the trigger context
    assert len(dispatch.calls) == 1
    assert dispatch.calls[0][1] == "operator-001"
    assert dispatch.calls[0][2] is context


def test_duplicate_fire_skips_audit_and_dispatch() -> None:
    repo = FakeFiredTriggersRepository()
    audit = FakeAuditPort()
    dispatch = _RecordingDispatch()

    # First fire (fresh) — same operator day/key.
    first = _daily_context()
    asyncio.run(
        fire_trigger(
            fired_triggers_repository=repo,
            audit_port=audit,
            broadcast_dispatch=dispatch,
            actor=_actor(),
            trigger_context=first,
            operator_timezone="UTC",
        )
    )
    # Second fire same day — duplicate; the idempotency key resolves to
    # the same operator-date string so insert_or_skip returns False.
    second = _daily_context()
    result = asyncio.run(
        fire_trigger(
            fired_triggers_repository=repo,
            audit_port=audit,
            broadcast_dispatch=dispatch,
            actor=_actor(),
            trigger_context=second,
            operator_timezone="UTC",
        )
    )

    assert result.status is FireTriggerStatus.ALREADY_FIRED
    assert result.trigger_id == str(second.trigger_id)
    # only the first fire audited and dispatched
    assert len(audit.events) == 1
    assert len(dispatch.calls) == 1


def test_manual_fire_always_fresh() -> None:
    """MANUAL triggers carry a null idempotency key — each fire is fresh."""
    repo = FakeFiredTriggersRepository()
    audit = FakeAuditPort()
    dispatch = _RecordingDispatch()

    def _manual() -> TriggerContext:
        return TriggerContext(
            trigger_type=BroadcastTriggerType.MANUAL,
            trigger_id=uuid4(),
            triggered_at="2026-05-28T06:00:00+00:00",
            metadata={"caller_note": "test"},
        )

    for _ in range(2):
        result = asyncio.run(
            fire_trigger(
                fired_triggers_repository=repo,
                audit_port=audit,
                broadcast_dispatch=dispatch,
                actor=_actor(),
                trigger_context=_manual(),
                operator_timezone="UTC",
            )
        )
        assert result.status is FireTriggerStatus.ACCEPTED

    assert len(audit.events) == 2
    assert len(dispatch.calls) == 2
