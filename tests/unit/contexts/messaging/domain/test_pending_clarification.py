"""Unit tests for the PendingClarification domain entity (D134, S47)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
    PendingClarificationStatus,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _pending(
    *,
    status: PendingClarificationStatus = PendingClarificationStatus.PENDING,
    resolved_at: datetime | None = None,
    expires_in: timedelta = timedelta(hours=24),
    target_cell: str = "manual_entry",
) -> PendingClarification:
    created = _now()
    return PendingClarification(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        user_id="operator",
        originating_channel="WHATSAPP",
        originating_user_address="+447700900123",
        originating_intake_id=uuid4(),
        proposed_intent={"intent_type": "add_data_point"},
        proposed_action_summary="add a goal to the Q3 portfolio review",
        status=status,
        target_cell=target_cell,
        created_at=created,
        expires_at=created + expires_in,
        resolved_at=resolved_at,
    )


def test_construction_happy_path() -> None:
    pending = _pending()
    assert pending.status is PendingClarificationStatus.PENDING
    assert pending.resolved_at is None
    assert pending.target_cell == "manual_entry"


def test_construction_rejects_empty_user_id() -> None:
    with pytest.raises(ValueError, match="user_id"):
        PendingClarification(
            id=uuid4(),
            tenant_id=uuid4(),
            jurisdiction="eu-west",
            user_id="",
            originating_channel="WHATSAPP",
            originating_user_address="+447700900123",
            originating_intake_id=uuid4(),
            proposed_intent={},
            proposed_action_summary="add a goal",
            status=PendingClarificationStatus.PENDING,
            target_cell="manual_entry",
            created_at=_now(),
            expires_at=_now() + timedelta(hours=24),
        )


def test_construction_rejects_resolved_at_on_pending() -> None:
    with pytest.raises(ValueError, match="resolved_at must be None while PENDING"):
        _pending(
            status=PendingClarificationStatus.PENDING,
            resolved_at=_now(),
        )


def test_construction_requires_resolved_at_on_terminal_status() -> None:
    with pytest.raises(ValueError, match="resolved_at must be set on terminal"):
        _pending(
            status=PendingClarificationStatus.RESOLVED,
            resolved_at=None,
        )


def test_construction_rejects_expires_at_at_or_before_created() -> None:
    base = _now()
    with pytest.raises(ValueError, match="expires_at must be strictly after"):
        PendingClarification(
            id=uuid4(),
            tenant_id=uuid4(),
            jurisdiction="eu-west",
            user_id="operator",
            originating_channel="WHATSAPP",
            originating_user_address="+447700900123",
            originating_intake_id=uuid4(),
            proposed_intent={},
            proposed_action_summary="add a goal",
            status=PendingClarificationStatus.PENDING,
            target_cell="manual_entry",
            created_at=base,
            expires_at=base,
        )


def test_construction_rejects_unknown_target_cell() -> None:
    with pytest.raises(ValueError, match="target_cell must be one of"):
        _pending(target_cell="not_a_cell")


def test_construction_accepts_every_known_target_cell() -> None:
    for known in (
        "manual_entry",
        "audit_conversation",
        "mirror_conversation",
        "dispatch_clarification",
    ):
        pending = _pending(target_cell=known)
        assert pending.target_cell == known


def test_resolve_preserves_target_cell() -> None:
    pending = _pending(target_cell="audit_conversation")
    resolved = pending.resolve(at=_now())
    assert resolved.target_cell == "audit_conversation"


def test_expire_preserves_target_cell() -> None:
    pending = _pending(target_cell="mirror_conversation")
    expired = pending.expire(at=_now())
    assert expired.target_cell == "mirror_conversation"


def test_resolve_transitions_pending_to_resolved() -> None:
    pending = _pending()
    resolved_at = _now()
    resolved = pending.resolve(at=resolved_at)
    assert resolved.status is PendingClarificationStatus.RESOLVED
    assert resolved.resolved_at == resolved_at
    assert resolved.id == pending.id
    # Original is unchanged (frozen).
    assert pending.status is PendingClarificationStatus.PENDING


def test_resolve_rejects_already_resolved() -> None:
    pending = _pending().resolve(at=_now())
    with pytest.raises(ValueError, match="cannot resolve a RESOLVED"):
        pending.resolve(at=_now())


def test_expire_transitions_pending_to_expired() -> None:
    pending = _pending()
    expired = pending.expire(at=_now())
    assert expired.status is PendingClarificationStatus.EXPIRED
    assert expired.resolved_at is not None


def test_expire_rejects_resolved_pending() -> None:
    pending = _pending().resolve(at=_now())
    with pytest.raises(ValueError, match="cannot expire a RESOLVED"):
        pending.expire(at=_now())
