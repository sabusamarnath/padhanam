"""Unit tests for the intake domain layer (D127, D128)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.intake.domain import (
    IntakePayload,
    IntakeRecord,
    IntakeSource,
    ManualEntryPayload,
)
from shared_kernel import ActorReference


def _payload() -> ManualEntryPayload:
    return ManualEntryPayload(raw_text="ship the S44b substrate")


def _intake_record(*, jurisdiction: str = "eu-west") -> IntakeRecord:
    return IntakeRecord(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction=jurisdiction,
        intake_source=IntakeSource.MANUAL_ENTRY,
        payload=_payload(),
        authored_by=ActorReference(user_id="operator"),
        created_at=datetime.now(timezone.utc),
    )


# --- ManualEntryPayload --------------------------------------------


def test_manual_entry_payload_happy_path() -> None:
    payload = ManualEntryPayload(
        raw_text="a goal", intent_hint="create-case"
    )
    assert payload.raw_text == "a goal"
    assert payload.intent_hint == "create-case"
    assert payload.linked_case_ids == ()


def test_manual_entry_payload_defaults() -> None:
    payload = ManualEntryPayload(raw_text="x")
    assert payload.intent_hint is None
    assert payload.linked_case_ids == ()


def test_manual_entry_payload_carries_linked_case_ids() -> None:
    cid = uuid4()
    payload = ManualEntryPayload(raw_text="x", linked_case_ids=(cid,))
    assert payload.linked_case_ids == (cid,)


def test_manual_entry_payload_empty_raw_text_rejected() -> None:
    with pytest.raises(ValueError, match="raw_text"):
        ManualEntryPayload(raw_text="")


def test_manual_entry_payload_blank_raw_text_rejected() -> None:
    with pytest.raises(ValueError, match="raw_text"):
        ManualEntryPayload(raw_text="   ")


def test_manual_entry_payload_is_frozen() -> None:
    payload = _payload()
    with pytest.raises(FrozenInstanceError):
        payload.raw_text = "other"  # type: ignore[misc]


def test_intake_payload_alias_is_manual_entry_payload() -> None:
    """At S44b IntakePayload is the single ManualEntryPayload variant."""
    assert IntakePayload is ManualEntryPayload


# --- IntakeSource --------------------------------------------------


def test_intake_source_phase_2a_value() -> None:
    assert IntakeSource.MANUAL_ENTRY.value == "MANUAL_ENTRY"
    assert IntakeSource("MANUAL_ENTRY") is IntakeSource.MANUAL_ENTRY


# --- IntakeRecord --------------------------------------------------


def test_intake_record_happy_path() -> None:
    record = _intake_record()
    assert record.intake_source is IntakeSource.MANUAL_ENTRY
    assert isinstance(record.payload, ManualEntryPayload)
    assert record.authored_by.user_id == "operator"


def test_intake_record_empty_jurisdiction_rejected() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        _intake_record(jurisdiction="")


def test_intake_record_is_frozen() -> None:
    record = _intake_record()
    with pytest.raises(FrozenInstanceError):
        record.jurisdiction = "us-east"  # type: ignore[misc]


def test_intake_record_value_equality() -> None:
    rid = uuid4()
    tid = uuid4()
    ts = datetime.now(timezone.utc)
    actor = ActorReference(user_id="operator")
    payload = ManualEntryPayload(raw_text="same")
    a = IntakeRecord(
        id=rid, tenant_id=tid, jurisdiction="eu-west",
        intake_source=IntakeSource.MANUAL_ENTRY, payload=payload,
        authored_by=actor, created_at=ts,
    )
    b = IntakeRecord(
        id=rid, tenant_id=tid, jurisdiction="eu-west",
        intake_source=IntakeSource.MANUAL_ENTRY, payload=payload,
        authored_by=actor, created_at=ts,
    )
    assert a == b
