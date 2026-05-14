"""AuditEventRecord — read-side projection of a tenant_audit row (D102, S36).

Mirrors the 13-column ``tenant_audit`` schema 1:1 per
``charter/schema.md``: ``id`` (UUID), ``tenant_id``, ``actor``,
``jurisdiction``, ``timestamp``, ``action_verb``,
``resource_type``, ``resource_id``, ``before_state``,
``after_state``, ``correlation_id``, ``previous_event_hash``,
``this_event_hash``. The same shape applies against both
destinations (per-tenant and control-plane) per D35 — the schemas
are column-for-column identical.

Coexists with ``contexts.audit.domain.events.AuditEvent`` which
is the write-side value object (no ``id`` field — Postgres
generates server-side via ``gen_random_uuid()`` and the write
adapter never reads it back). Two coexisting value objects
mirror the same-shape pattern at run_history (``AgentRunRecord``
write-side aggregate versus ``RunRecord`` read-side aggregate).
Per D102 alternative (b)'s reasoning, the destination is a
port-method parameter rather than a field on this record; the
adapter's destination routing is opaque to consumers.

Frozen dataclass (not Pydantic v2): pattern-symmetry with
``AuditEvent`` and with ``RunRecord`` at run_history. The
shared_kernel principle ("never Pydantic") scopes to
shared_kernel only, but the codebase pattern at the
domain-value-object layer consistently favours frozen
dataclasses over Pydantic models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


_HEX_CHARS: frozenset[str] = frozenset("0123456789abcdef")


def _is_64_lowercase_hex(value: str) -> bool:
    return len(value) == 64 and all(c in _HEX_CHARS for c in value)


@dataclass(frozen=True)
class AuditEventRecord:
    """One ``tenant_audit`` row projected for read-side consumers.

    Construction-time invariants mirror the schema-layer
    constraints and the hash-chain shape from D22:

    1. ``actor``, ``jurisdiction``, ``action_verb``,
       ``resource_type``, ``resource_id``, ``correlation_id``
       all non-empty (mirrors NOT NULL on text columns where
       empty strings would defeat the column's purpose).
    2. ``previous_event_hash`` and ``this_event_hash`` are
       64 lowercase hex characters.
    3. ``tenant_id`` shape: control-plane rows carry the empty
       string per D35 sentinel; per-tenant rows carry the
       routed tenant's id. No constraint at the domain layer
       because the destination context disambiguates.

    The reader adapter constructs ``AuditEventRecord`` instances
    from row mappings; consumers receive immutable records.
    """

    id: UUID
    tenant_id: str
    actor: str
    jurisdiction: str
    timestamp: datetime
    action_verb: str
    resource_type: str
    resource_id: str
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    correlation_id: str
    previous_event_hash: str
    this_event_hash: str

    def __post_init__(self) -> None:
        for field_name in (
            "actor",
            "jurisdiction",
            "action_verb",
            "resource_type",
            "resource_id",
            "correlation_id",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"AuditEventRecord.{field_name} must be a non-empty "
                    f"string; got {value!r}"
                )
        for hash_field in ("previous_event_hash", "this_event_hash"):
            value = getattr(self, hash_field)
            if not _is_64_lowercase_hex(value):
                raise ValueError(
                    f"AuditEventRecord.{hash_field} must be 64 lowercase "
                    f"hex characters; got {value!r}"
                )


__all__ = ["AuditEventRecord"]
