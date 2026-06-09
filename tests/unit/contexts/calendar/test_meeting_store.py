"""Unit tests for the Meeting store adapter codec + guards (D148).

Exercises the envelope-encryption content codec and row mapping end to
end without a live database, plus the bound-tenant defence-in-depth guard
and the pgvector literal format. Live SQL is operator-smoke-verified.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from padhanam.security import crypto
from shared_kernel.tenant_context import TenantContext

from contexts.calendar.adapters.outbound.postgres.meeting_store import (
    PostgresMeetingStore,
    _aad_context,
    _format_vector_literal,
    _row_to_meeting,
    deserialize_meeting_content,
    serialize_meeting_content,
)
from contexts.calendar.domain.meeting import (
    Meeting,
    MeetingAttendee,
    MeetingStatus,
)

_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=timezone.utc)
_TENANT = "11111111-1111-1111-1111-111111111111"


def _meeting(tenant_id: str = _TENANT) -> Meeting:
    return Meeting(
        id=uuid4(),
        tenant_id=__import__("uuid").UUID(tenant_id),
        jurisdiction="eu-west",
        google_event_id="evt-1",
        status=MeetingStatus.CONFIRMED,
        title="Board sync",
        description="Quarterly review",
        location="Room 4",
        attendees=(MeetingAttendee("ada@example.com", "Ada", "accepted"),),
        organizer_email="chair@example.com",
        start_at=_NOW,
        end_at=_NOW,
        start_raw="2026-05-28T12:00:00+00:00",
        end_raw="2026-05-28T13:00:00+00:00",
        source_updated_at=_NOW,
        recurring_event_id=None,
        html_link="https://calendar.google.com/evt-1",
        content_hash="abc123",
        created_at=_NOW,
        updated_at=_NOW,
    )


def test_content_codec_encrypt_decrypt_round_trip() -> None:
    meeting = _meeting()
    plaintext = serialize_meeting_content(meeting)
    encrypted = crypto.encrypt_field(plaintext, _aad_context(meeting.tenant_id))
    recovered = deserialize_meeting_content(
        crypto.decrypt_field(encrypted, _aad_context(meeting.tenant_id))
    )
    assert recovered["title"] == "Board sync"
    assert recovered["location"] == "Room 4"
    assert recovered["attendees"][0]["display_name"] == "Ada"


def test_cross_tenant_aad_decrypt_fails() -> None:
    meeting = _meeting()
    plaintext = serialize_meeting_content(meeting)
    encrypted = crypto.encrypt_field(plaintext, _aad_context(meeting.tenant_id))
    other_tenant = "22222222-2222-2222-2222-222222222222"
    with pytest.raises(Exception):
        crypto.decrypt_field(encrypted, _aad_context(other_tenant))


def test_row_to_meeting_reconstructs_encrypted_content() -> None:
    meeting = _meeting()
    encrypted = crypto.encrypt_field(
        serialize_meeting_content(meeting), _aad_context(meeting.tenant_id)
    )
    row = {
        "id": str(meeting.id),
        "tenant_id": _TENANT,
        "jurisdiction": "eu-west",
        "calendar_id": "cal-personal",
        "google_event_id": "evt-1",
        "status": "confirmed",
        "start_at": _NOW,
        "end_at": _NOW,
        "start_raw": meeting.start_raw,
        "end_raw": meeting.end_raw,
        "source_updated_at": _NOW,
        "recurring_event_id": None,
        "html_link": meeting.html_link,
        "content_hash": "abc123",
        "enc_wrapped_dek": encrypted.wrapped_dek,
        "enc_dek_wrap_nonce": encrypted.dek_wrap_nonce,
        "enc_ciphertext": encrypted.ciphertext,
        "enc_nonce": encrypted.nonce,
        "enc_key_version": encrypted.key_version,
        "created_at": _NOW,
        "updated_at": _NOW,
        "cancelled_at": None,
    }
    rebuilt = _row_to_meeting(row, tenant_id=_TENANT)
    assert rebuilt.title == "Board sync"
    assert rebuilt.attendees[0].email == "ada@example.com"
    assert rebuilt.status is MeetingStatus.CONFIRMED


def test_tombstoned_row_has_no_content() -> None:
    row = {
        "id": str(uuid4()),
        "tenant_id": _TENANT,
        "jurisdiction": "eu-west",
        "calendar_id": "cal-personal",
        "google_event_id": "evt-x",
        "status": "cancelled",
        "start_at": None,
        "end_at": None,
        "start_raw": None,
        "end_raw": None,
        "source_updated_at": None,
        "recurring_event_id": None,
        "html_link": None,
        "content_hash": None,
        "enc_wrapped_dek": None,
        "enc_dek_wrap_nonce": None,
        "enc_ciphertext": None,
        "enc_nonce": None,
        "enc_key_version": None,
        "created_at": _NOW,
        "updated_at": _NOW,
        "cancelled_at": _NOW,
    }
    rebuilt = _row_to_meeting(row, tenant_id=_TENANT)
    assert rebuilt.is_cancelled
    assert rebuilt.title is None
    assert rebuilt.attendees == ()


def test_upsert_rejects_cross_tenant_context() -> None:
    async def _resolver(_tenant_id):  # pragma: no cover - must not be called
        raise AssertionError("resolver should not be reached past the guard")

    store = PostgresMeetingStore(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=_TENANT,
    )
    other = TenantContext(
        tenant_id="99999999-9999-9999-9999-999999999999",
        jurisdiction="eu-west",
        cost_attribution_id="cost",
    )
    with pytest.raises(ValueError, match="does not match adapter's bound tenant"):
        asyncio.run(store.upsert_meeting(tenant_context=other, meeting=_meeting()))


def test_format_vector_literal() -> None:
    assert _format_vector_literal([0.1, 0.2, 0.3]) == "[0.1,0.2,0.3]"
