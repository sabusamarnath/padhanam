"""FiredTrigger value object — record of a successful trigger fire (D147, S54).

Represents one row of the fired_triggers table. The write path is
through the FiredTriggersRepository's ``insert_or_skip`` method that
returns a boolean fresh-vs-conflict outcome; the read shape exists
for diagnostic surfaces (last firing per user per trigger type)
that may emerge at Phase 2-B+ if multi-tenant scale calls for it.

Per D16 domain code is framework-free — stdlib only; no Pydantic,
no vendor SDKs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class FiredTrigger:
    """One row of the fired_triggers table per D147.

    ``trigger_type`` is the string value of the
    ``shared_kernel.broadcast_flow.BroadcastTriggerType`` enum (one
    of ``daily_scheduled``, ``threshold_crossed``, ``calendar_event``,
    ``email_received``, ``manual``). The enum is not imported to
    avoid coupling the messaging-domain layer to shared_kernel's
    broadcast-flow abstraction; the value-object's responsibility is
    persistence-shape representation, not enum-validation.

    ``idempotency_key`` is nullable per D147 — MANUAL triggers
    typically carry no idempotency key, and the UNIQUE constraint at
    the persistence layer accommodates multiple nulls per Postgres
    semantics.
    """

    id: UUID
    tenant_id: UUID
    user_id: str
    trigger_type: str
    idempotency_key: str | None
    fired_at: datetime

    def __post_init__(self) -> None:
        if not self.user_id or not self.user_id.strip():
            raise ValueError("FiredTrigger.user_id must be non-empty")
        if not self.trigger_type or not self.trigger_type.strip():
            raise ValueError("FiredTrigger.trigger_type must be non-empty")


__all__ = ["FiredTrigger"]
