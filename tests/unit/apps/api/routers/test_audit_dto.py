"""Unit tests for the audit HTTP DTOs (D103, S37).

Round-trip conversion: domain ``AuditEventRecord`` →
``AuditEventRecordDTO`` via ``model_validate``; hash validators fire
on malformed hex; the page envelope packages events + cursor +
chain-integrity verification.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from apps.api.routers._audit_dto import (
    AuditEventListPageDTO,
    AuditEventRecordDTO,
    ChainIntegrityVerificationDTO,
)
from contexts.audit.domain.audit_event_record import AuditEventRecord
from contexts.audit.domain.chain_integrity import ChainIntegrityVerification


_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _record() -> AuditEventRecord:
    return AuditEventRecord(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        tenant_id="tenant-a",
        actor="user:alice",
        jurisdiction="UK",
        timestamp=datetime(2026, 5, 14, 10, 30, 0, tzinfo=timezone.utc),
        action_verb="agent.invoke.start",
        resource_type="agent",
        resource_id="agent-1",
        before_state={},
        after_state={"input": "hi"},
        correlation_id="corr-1",
        previous_event_hash=_HASH_A,
        this_event_hash=_HASH_B,
    )


def test_audit_event_record_dto_round_trips_from_domain_record() -> None:
    dto = AuditEventRecordDTO.model_validate(_record())
    assert dto.tenant_id == "tenant-a"
    assert dto.action_verb == "agent.invoke.start"
    assert dto.after_state == {"input": "hi"}
    assert dto.previous_event_hash == _HASH_A
    assert dto.this_event_hash == _HASH_B


def test_audit_event_record_dto_serialises_jsonb_columns_as_dicts() -> None:
    dto = AuditEventRecordDTO.model_validate(_record())
    json_payload = dto.model_dump(mode="json")
    assert json_payload["before_state"] == {}
    assert json_payload["after_state"] == {"input": "hi"}
    assert isinstance(json_payload["timestamp"], str)


def test_audit_event_record_dto_rejects_non_hex_hash() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditEventRecordDTO(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            tenant_id="tenant-a",
            actor="user:alice",
            jurisdiction="UK",
            timestamp=datetime(2026, 5, 14, 10, 30, 0, tzinfo=timezone.utc),
            action_verb="agent.invoke.start",
            resource_type="agent",
            resource_id="agent-1",
            before_state={},
            after_state={},
            correlation_id="corr-1",
            previous_event_hash="NOT-HEX",
            this_event_hash=_HASH_B,
        )
    assert "hex" in str(exc_info.value).lower()


def test_chain_integrity_verification_dto_round_trips_verified() -> None:
    domain = ChainIntegrityVerification(status="verified")
    dto = ChainIntegrityVerificationDTO.model_validate(domain)
    assert dto.status == "verified"
    assert dto.broken_at_id is None


def test_chain_integrity_verification_dto_round_trips_broken_at_row() -> None:
    bid = UUID("00000000-0000-0000-0000-000000000099")
    domain = ChainIntegrityVerification(status="broken_at_row", broken_at_id=bid)
    dto = ChainIntegrityVerificationDTO.model_validate(domain)
    assert dto.status == "broken_at_row"
    assert dto.broken_at_id == bid


def test_audit_event_list_page_dto_carries_events_cursor_and_integrity() -> None:
    page = AuditEventListPageDTO(
        events=[AuditEventRecordDTO.model_validate(_record())],
        next_cursor="opaque-cursor-string",
        chain_integrity=ChainIntegrityVerificationDTO(status="verified"),
    )
    payload = page.model_dump(mode="json")
    assert len(payload["events"]) == 1
    assert payload["next_cursor"] == "opaque-cursor-string"
    assert payload["chain_integrity"]["status"] == "verified"
