"""Unit tests for TriggerContext typed metadata helpers (D146, D147, S54).

Per S54 pre-write reconciliation Finding 3, TriggerContext.metadata
stays as ``dict[str, Any]``; the typed metadata classes are
convenience constructors that serialise into that dict. These tests
pin the serialisation surface and confirm the S53 TriggerContext
construction is unchanged.
"""

from __future__ import annotations

from uuid import uuid4

from shared_kernel.broadcast_flow import (
    BroadcastTriggerType,
    DailyScheduledMetadata,
    ManualMetadata,
    TriggerContext,
)


def test_daily_scheduled_metadata_serialises_empty() -> None:
    assert DailyScheduledMetadata().to_metadata() == {}


def test_manual_metadata_without_note_serialises_empty() -> None:
    assert ManualMetadata().to_metadata() == {}


def test_manual_metadata_with_note_serialises_note() -> None:
    md = ManualMetadata(caller_note="operator test fire")
    assert md.to_metadata() == {"caller_note": "operator test fire"}


def test_trigger_context_still_accepts_dict_metadata() -> None:
    """The S53 open-dict metadata slot is unchanged (backward compat)."""
    context = TriggerContext(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
        trigger_id=uuid4(),
        triggered_at="2026-05-28T06:00:00+00:00",
        metadata=DailyScheduledMetadata().to_metadata(),
    )
    assert context.metadata == {}


def test_trigger_context_carries_manual_note_via_dict() -> None:
    context = TriggerContext(
        trigger_type=BroadcastTriggerType.MANUAL,
        trigger_id=uuid4(),
        triggered_at="2026-05-28T06:00:00+00:00",
        metadata=ManualMetadata(caller_note="note").to_metadata(),
    )
    assert context.metadata == {"caller_note": "note"}
