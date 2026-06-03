"""Citation-time audit-snapshot evidence for calendar citations (D148 option b, D21, P15, S55b-2).

A `Meeting` is the platform's first mutable cited source: the live row is
overwritten on each refresh (D149), so citing it requires freezing the
evidence at citation time (the two-store split, D148 option b). When the
calendar-conversation cell composes a cited response, it emits a
`meeting_citation` audit event whose `after_state` carries an immutable
snapshot of each cited Meeting's payload. Because the audit chain is
append-only and hash-chained (D102/D110), the snapshot survives the next
refresh's overwrite of the live row.

**No plaintext leak (D21).** Audit `after_state` is plaintext JSONB at
rest (no audit-layer encryption), and the meetings table deliberately
envelope-encrypts the sensitive content (title, description, location,
attendees, organizer — D21). So the snapshot must not put that content
in plaintext into `after_state`: the sensitive fields are encrypted with
the same `crypto.encrypt_field` envelope mechanism (a citation-scoped
AAD) and only the ciphertext components plus non-sensitive metadata
(event id, status, content hash, timestamps, attendee count) land in the
after_state. The content_hash is the integrity anchor; the encrypted blob
is the recoverable evidence (decrypt with the tenant key). A unit test
asserts no plaintext title/description/location reaches the after_state.

This mechanism is calendar-local, not a shared citation-evidence hook —
deferred to the second mutable cited source per the two-threshold rule
(Email at S56 is append-only, not a second mutable case). See
`charter/architecture.md` "Citation-time audit-snapshot evidence".
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from contexts.audit.domain.events import (
    GENESIS_HASH,
    AuditEvent,
    compute_event_hash,
)
from contexts.calendar.domain.meeting import Meeting
from padhanam.security import crypto
from shared_kernel import ActorReference, TenantContext

RESOURCE_TYPE_MEETING_CITATION: str = "meeting_citation"
ACTION_MEETING_CITATION_EMIT: str = "calendar_conversation.citation.emit"

# AAD field tag binding the citation snapshot's encryption to its purpose
# (distinct from the meetings store's content field) so a citation blob
# cannot be transplanted into the store's decrypt path or vice versa.
_CITATION_AAD_FIELD: str = "meeting_citation_snapshot"


def _aad(tenant_id: object) -> dict[str, str]:
    return {"tenant_id": str(tenant_id), "field": _CITATION_AAD_FIELD}


def _serialize_sensitive(meeting: Meeting) -> bytes:
    """The D21-protected content (title/description/location/attendees/organizer)."""
    payload = {
        "title": meeting.title,
        "description": meeting.description,
        "location": meeting.location,
        "organizer_email": meeting.organizer_email,
        "attendees": [
            {
                "email": a.email,
                "display_name": a.display_name,
                "response_status": a.response_status,
                "organizer": a.organizer,
            }
            for a in meeting.attendees
        ],
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def meeting_citation_snapshot(
    meeting: Meeting, *, tenant_id: object
) -> dict[str, object]:
    """An immutable, plaintext-free evidence snapshot of a cited Meeting.

    Non-sensitive metadata is plaintext; the D21-protected content is
    envelope-encrypted and only its ciphertext components are stored
    (base64 for JSONB). Decryptable with the tenant key + the citation AAD.
    """
    enc = crypto.encrypt_field(_serialize_sensitive(meeting), _aad(tenant_id))
    return {
        "meeting_id": str(meeting.id),
        "google_event_id": meeting.google_event_id,
        "status": meeting.status.value,
        "content_hash": meeting.content_hash,
        "start_at": _iso(meeting.start_at),
        "end_at": _iso(meeting.end_at),
        "source_updated_at": _iso(meeting.source_updated_at),
        "attendee_count": len(meeting.attendees),
        "enc_content": {
            "wrapped_dek": base64.b64encode(enc.wrapped_dek).decode("ascii"),
            "dek_wrap_nonce": base64.b64encode(enc.dek_wrap_nonce).decode("ascii"),
            "ciphertext": base64.b64encode(enc.ciphertext).decode("ascii"),
            "nonce": base64.b64encode(enc.nonce).decode("ascii"),
            "key_version": enc.key_version,
        },
    }


def decrypt_citation_snapshot(
    snapshot: dict[str, object], *, tenant_id: object
) -> dict[str, object]:
    """Recover the cited Meeting's content from a snapshot (the evidence read-side)."""
    enc_block = snapshot["enc_content"]
    assert isinstance(enc_block, dict)
    field = crypto.EncryptedField(
        wrapped_dek=base64.b64decode(enc_block["wrapped_dek"]),
        dek_wrap_nonce=base64.b64decode(enc_block["dek_wrap_nonce"]),
        ciphertext=base64.b64decode(enc_block["ciphertext"]),
        nonce=base64.b64decode(enc_block["nonce"]),
        key_version=int(enc_block["key_version"]),
    )
    plaintext = crypto.decrypt_field(field, _aad(tenant_id))
    return json.loads(plaintext.decode("utf-8"))


def draft_meeting_citation_event(
    *,
    tenant_context: TenantContext,
    actor: ActorReference,
    meetings: tuple[Meeting, ...],
    emitted_at: str | None = None,
    correlation_id: str = "",
) -> AuditEvent:
    """Draft the citation-emission audit event freezing the cited Meetings.

    Resource type ``meeting_citation``; the resource_id is the primary
    cited Meeting's id. ``after_state`` carries the per-Meeting snapshots
    (sensitive content encrypted; metadata plaintext) — the immutable
    evidence record. The adapter recomputes the chain hashes inside its
    locking transaction per D37; the placeholder here is a draft value.
    """
    timestamp = emitted_at or datetime.now(timezone.utc).isoformat()
    snapshots = [
        meeting_citation_snapshot(m, tenant_id=tenant_context.tenant_id)
        for m in meetings
    ]
    resource_id = str(meetings[0].id) if meetings else ""
    after_state: dict[str, object] = {
        "cited_meetings": snapshots,
        "cited_count": len(snapshots),
    }
    draft_hash = compute_event_hash(
        actor=actor.user_id,
        tenant_id=tenant_context.tenant_id,
        jurisdiction=tenant_context.jurisdiction,
        timestamp=timestamp,
        action_verb=ACTION_MEETING_CITATION_EMIT,
        resource_type=RESOURCE_TYPE_MEETING_CITATION,
        resource_id=resource_id,
        before_state={},
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
    )
    return AuditEvent(
        actor=actor.user_id,
        tenant_id=tenant_context.tenant_id,
        jurisdiction=tenant_context.jurisdiction,
        timestamp=timestamp,
        action_verb=ACTION_MEETING_CITATION_EMIT,
        resource_type=RESOURCE_TYPE_MEETING_CITATION,
        resource_id=resource_id,
        before_state={},
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
        this_event_hash=draft_hash,
    )


__all__ = [
    "ACTION_MEETING_CITATION_EMIT",
    "RESOURCE_TYPE_MEETING_CITATION",
    "decrypt_citation_snapshot",
    "draft_meeting_citation_event",
    "meeting_citation_snapshot",
]
