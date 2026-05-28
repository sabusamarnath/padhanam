"""Unit tests for the BROADCAST_INITIATED audit event helper (D147, S54)."""

from __future__ import annotations

from uuid import uuid4

from contexts.audit.domain.events import GENESIS_HASH, compute_event_hash
from contexts.messaging.application.audit_events import (
    ACTION_BROADCAST_INITIATED,
    RESOURCE_TYPE_BROADCAST,
    draft_broadcast_initiated_event,
)
from shared_kernel import ActorReference, TenantContext


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id="11111111-1111-1111-1111-111111111111",
        jurisdiction="eu-west",
        cost_attribution_id="11111111-1111-1111-1111-111111111111",
    )


def test_draft_broadcast_initiated_event_shape() -> None:
    """The draft event carries the broadcast resource type and action verb."""
    trigger_id = uuid4()
    event = draft_broadcast_initiated_event(
        tenant_context=_ctx(),
        actor=ActorReference(user_id="operator-001"),
        trigger_id=trigger_id,
        trigger_type="daily_scheduled",
        user_id="operator-001",
        triggered_at="2026-05-28T06:00:00+00:00",
    )
    assert event.resource_type == RESOURCE_TYPE_BROADCAST
    assert event.action_verb == ACTION_BROADCAST_INITIATED
    assert event.resource_id == str(trigger_id)
    assert event.actor == "operator-001"
    assert event.before_state == {}
    assert event.after_state["trigger_id"] == str(trigger_id)
    assert event.after_state["trigger_type"] == "daily_scheduled"
    assert event.after_state["user_id"] == "operator-001"


def test_draft_broadcast_initiated_event_hash_is_recomputable() -> None:
    """The draft hash matches a recomputation from the event payload."""
    trigger_id = uuid4()
    event = draft_broadcast_initiated_event(
        tenant_context=_ctx(),
        actor=ActorReference(user_id="operator-001"),
        trigger_id=trigger_id,
        trigger_type="daily_scheduled",
        user_id="operator-001",
        triggered_at="2026-05-28T06:00:00+00:00",
    )
    recomputed = compute_event_hash(
        actor=event.actor,
        tenant_id=event.tenant_id,
        jurisdiction=event.jurisdiction,
        timestamp=event.timestamp,
        action_verb=event.action_verb,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        before_state=event.before_state,
        after_state=event.after_state,
        correlation_id=event.correlation_id,
        previous_event_hash=GENESIS_HASH,
    )
    assert event.this_event_hash == recomputed


def test_draft_broadcast_initiated_event_threads_correlation_id() -> None:
    event = draft_broadcast_initiated_event(
        tenant_context=_ctx(),
        actor=ActorReference(user_id="operator-001"),
        trigger_id=uuid4(),
        trigger_type="manual",
        user_id="operator-001",
        triggered_at="2026-05-28T06:00:00+00:00",
        correlation_id="corr-123",
    )
    assert event.correlation_id == "corr-123"
