"""Unit tests for PendingClarification lifecycle use cases (D134, S47).

Covers the create-then-expire-prior invariant, the resolve and expire
transitions, audit-event emission, and authorisation enforcement on
each use case.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from contexts.audit.domain.events import AuditEvent

from contexts.messaging.application.create_pending_clarification import (
    create_pending_clarification,
)
from contexts.messaging.application.expire_pending_clarification import (
    expire_pending_clarification,
)
from contexts.messaging.application.resolve_pending_clarification import (
    resolve_pending_clarification,
)
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
    PendingClarificationStatus,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import (
    AuthorisationDenied,
    MESSAGING_PENDING_CLARIFICATION_CREATE,
    MESSAGING_PENDING_CLARIFICATION_EXPIRE,
    MESSAGING_PENDING_CLARIFICATION_RESOLVE,
    ROLE_OPERATOR,
    authorisations_for_roles,
)


_TENANT_UUID = uuid4()
_TENANT_ID = str(_TENANT_UUID)


def _actor(*, missing: str | None = None) -> ActorContext:
    role_list = frozenset({ROLE_OPERATOR})
    granted = authorisations_for_roles(role_list)
    if missing is not None:
        granted = frozenset(granted - {missing})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT_ID,
            jurisdiction="eu-west",
            cost_attribution_id=_TENANT_ID,
        ),
        actor_id="operator",
        role_list=role_list,
        authorisation_set=granted,
    )


class _FakeRepo:
    def __init__(self) -> None:
        self.pendings: dict[UUID, PendingClarification] = {}

    async def save(self, *, tenant_context, pending) -> None:
        self.pendings[pending.id] = pending

    async def update_status(self, *, tenant_context, pending) -> None:
        self.pendings[pending.id] = pending

    async def get_by_id(self, *, tenant_context, pending_id: UUID):
        return self.pendings.get(pending_id)

    async def get_active_for_user(self, *, tenant_context, user_id: str):
        for p in self.pendings.values():
            if (
                str(p.tenant_id) == tenant_context.tenant_id
                and p.user_id == user_id
                and p.status is PendingClarificationStatus.PENDING
            ):
                return p
        return None


class _FakeAuditPort:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def emit(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event


def test_create_persists_pending_and_emits_create_event() -> None:
    repo = _FakeRepo()
    audit = _FakeAuditPort()

    pending = asyncio.run(
        create_pending_clarification(
            repository=repo,
            audit_port=audit,
            actor=_actor(),
            user_id="operator",
            originating_channel="WHATSAPP",
            originating_user_address="+447700900123",
            originating_intake_id=uuid4(),
            proposed_intent={"intent_type": "add_data_point"},
            proposed_action_summary="add a goal to Q3 review",
            target_cell="manual_entry",
        )
    )

    assert pending.status is PendingClarificationStatus.PENDING
    assert pending.id in repo.pendings
    assert len(audit.events) == 1
    assert (
        audit.events[0].action_verb
        == "messaging.pending_clarification.create"
    )


def test_create_expires_any_prior_pending_for_same_user() -> None:
    """D134 invariant — operator-side expiry sweep before insert."""
    repo = _FakeRepo()
    audit = _FakeAuditPort()
    actor = _actor()

    first = asyncio.run(
        create_pending_clarification(
            repository=repo,
            audit_port=audit,
            actor=actor,
            user_id="operator",
            originating_channel="WHATSAPP",
            originating_user_address="+447700900123",
            originating_intake_id=uuid4(),
            proposed_intent={"intent_type": "add_data_point"},
            proposed_action_summary="first proposal",
            target_cell="manual_entry",
        )
    )
    second = asyncio.run(
        create_pending_clarification(
            repository=repo,
            audit_port=audit,
            actor=actor,
            user_id="operator",
            originating_channel="WHATSAPP",
            originating_user_address="+447700900123",
            originating_intake_id=uuid4(),
            proposed_intent={"intent_type": "add_data_point"},
            proposed_action_summary="second proposal",
            target_cell="manual_entry",
        )
    )

    # The first pending is now EXPIRED; only the second is PENDING.
    assert repo.pendings[first.id].status is PendingClarificationStatus.EXPIRED
    assert repo.pendings[second.id].status is PendingClarificationStatus.PENDING
    # Three audit events: create(1), expire(1), create(2).
    verbs = [e.action_verb for e in audit.events]
    assert verbs == [
        "messaging.pending_clarification.create",
        "messaging.pending_clarification.expire",
        "messaging.pending_clarification.create",
    ]


def test_resolve_transitions_to_resolved_and_emits_event() -> None:
    repo = _FakeRepo()
    audit = _FakeAuditPort()
    actor = _actor()
    pending = asyncio.run(
        create_pending_clarification(
            repository=repo,
            audit_port=audit,
            actor=actor,
            user_id="operator",
            originating_channel="WHATSAPP",
            originating_user_address="+447700900123",
            originating_intake_id=uuid4(),
            proposed_intent={"intent_type": "add_data_point"},
            proposed_action_summary="proposal",
            target_cell="manual_entry",
        )
    )

    resolved = asyncio.run(
        resolve_pending_clarification(
            repository=repo,
            audit_port=audit,
            actor=actor,
            pending=pending,
            resolution="confirmed",
        )
    )

    assert resolved.status is PendingClarificationStatus.RESOLVED
    assert resolved.resolved_at is not None
    assert (
        audit.events[-1].action_verb
        == "messaging.pending_clarification.resolve"
    )
    assert audit.events[-1].after_state["resolution"] == "confirmed"


def test_expire_transitions_to_expired_and_emits_event() -> None:
    repo = _FakeRepo()
    audit = _FakeAuditPort()
    actor = _actor()
    pending = asyncio.run(
        create_pending_clarification(
            repository=repo,
            audit_port=audit,
            actor=actor,
            user_id="operator",
            originating_channel="WHATSAPP",
            originating_user_address="+447700900123",
            originating_intake_id=uuid4(),
            proposed_intent={"intent_type": "add_data_point"},
            proposed_action_summary="proposal",
            target_cell="manual_entry",
        )
    )

    expired = asyncio.run(
        expire_pending_clarification(
            repository=repo,
            audit_port=audit,
            actor=actor,
            pending=pending,
        )
    )

    assert expired.status is PendingClarificationStatus.EXPIRED
    assert (
        audit.events[-1].action_verb
        == "messaging.pending_clarification.expire"
    )


def test_create_denied_without_permission() -> None:
    repo = _FakeRepo()
    audit = _FakeAuditPort()
    with pytest.raises(AuthorisationDenied):
        asyncio.run(
            create_pending_clarification(
                repository=repo,
                audit_port=audit,
                actor=_actor(
                    missing=MESSAGING_PENDING_CLARIFICATION_CREATE
                ),
                user_id="operator",
                originating_channel="WHATSAPP",
                originating_user_address="+447700900123",
                originating_intake_id=uuid4(),
                proposed_intent={},
                proposed_action_summary="proposal",
                target_cell="manual_entry",
            )
        )


def test_resolve_denied_without_permission() -> None:
    repo = _FakeRepo()
    audit = _FakeAuditPort()
    pending = asyncio.run(
        create_pending_clarification(
            repository=repo,
            audit_port=audit,
            actor=_actor(),
            user_id="operator",
            originating_channel="WHATSAPP",
            originating_user_address="+447700900123",
            originating_intake_id=uuid4(),
            proposed_intent={},
            proposed_action_summary="proposal",
            target_cell="manual_entry",
        )
    )
    with pytest.raises(AuthorisationDenied):
        asyncio.run(
            resolve_pending_clarification(
                repository=repo,
                audit_port=audit,
                actor=_actor(
                    missing=MESSAGING_PENDING_CLARIFICATION_RESOLVE
                ),
                pending=pending,
                resolution="confirmed",
            )
        )


def test_expire_denied_without_permission() -> None:
    repo = _FakeRepo()
    audit = _FakeAuditPort()
    pending = asyncio.run(
        create_pending_clarification(
            repository=repo,
            audit_port=audit,
            actor=_actor(),
            user_id="operator",
            originating_channel="WHATSAPP",
            originating_user_address="+447700900123",
            originating_intake_id=uuid4(),
            proposed_intent={},
            proposed_action_summary="proposal",
            target_cell="manual_entry",
        )
    )
    with pytest.raises(AuthorisationDenied):
        asyncio.run(
            expire_pending_clarification(
                repository=repo,
                audit_port=audit,
                actor=_actor(
                    missing=MESSAGING_PENDING_CLARIFICATION_EXPIRE
                ),
                pending=pending,
            )
        )
