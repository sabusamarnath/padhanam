"""Pydantic response DTOs for the audit HTTP routes (D103, S37).

Field-for-field mirror of the audit-event domain records. The HTTP
boundary preserves the storage-versus-render discipline established at
D96 by declining to flatten, project, or rename fields. JSONB columns
(``before_state``, ``after_state``) surface as ``dict[str, Any]``;
``timestamp`` surfaces as ISO-8601 string via Pydantic v2 defaults;
hashes surface as hex strings with format validation per D103.

Pydantic v2 conventions mirror the run-history precedent at
``apps/api/routers/_run_history_dto.py``:

- ``model_config = ConfigDict(from_attributes=True)`` so domain
  records pass through ``AuditEventRecordDTO.model_validate(record)``
  cleanly without manual field mapping.
- ``UUID`` and ``datetime`` use Pydantic v2 defaults (canonical hex
  for UUID, ISO 8601 for datetime).
- ``chain_integrity`` on the page envelope is a nested DTO with the
  status discriminator preserved at the wire format.
- ``next_cursor`` on the page envelope is the opaque base64-of-JSON
  string from ``contexts.audit.application.cursor``; route handlers
  encode the domain ``AuditEventListCursor`` before constructing the
  DTO. Consumers treat it as a black box.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


_HEX_CHARS: frozenset[str] = frozenset("0123456789abcdef")


def _is_64_lowercase_hex(value: str) -> bool:
    return len(value) == 64 and all(c in _HEX_CHARS for c in value)


class AuditEventRecordDTO(BaseModel):
    """Mirrors ``AuditEventRecord`` 1:1 per D103.

    All 13 fields surface. ``before_state`` and ``after_state``
    JSONB columns surface as ``dict[str, Any]``;
    ``previous_event_hash`` and ``this_event_hash`` carry hex-string
    format validation matching the domain-layer invariant.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: str
    actor: str
    jurisdiction: str
    timestamp: datetime
    action_verb: str
    resource_type: str
    resource_id: str
    before_state: dict[str, Any] = Field(default_factory=dict)
    after_state: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str
    previous_event_hash: str
    this_event_hash: str

    @field_validator("previous_event_hash", "this_event_hash")
    @classmethod
    def _hash_is_hex(cls, value: str) -> str:
        if not _is_64_lowercase_hex(value):
            raise ValueError(
                "hash must be 64 lowercase hex characters; "
                f"got {value!r}"
            )
        return value


class ChainIntegrityVerificationDTO(BaseModel):
    """Mirrors ``ChainIntegrityVerification`` per D103.

    Discriminator on ``status``; ``broken_at_id`` is required when
    ``status == 'broken_at_row'`` and prohibited otherwise (the
    domain dataclass enforces this; Pydantic surfaces the field as
    optional and downstream readers branch on ``status``).
    """

    model_config = ConfigDict(from_attributes=True)

    status: Literal["verified", "broken_at_row", "partial"]
    broken_at_id: UUID | None = None


class AuditEventListPageDTO(BaseModel):
    """Envelope for ``GET /audit/events`` and ``GET /platform/audit/events`` per D103.

    Carries the page of events, the optional next-cursor string
    (opaque base64-of-JSON shape from
    ``contexts.audit.application.cursor``), and the page-level
    chain integrity verification. Consumers treat ``next_cursor``
    as a black box and pass it back verbatim on the next request.
    """

    events: list[AuditEventRecordDTO]
    next_cursor: str | None = None
    chain_integrity: ChainIntegrityVerificationDTO


__all__ = [
    "AuditEventListPageDTO",
    "AuditEventRecordDTO",
    "ChainIntegrityVerificationDTO",
]
