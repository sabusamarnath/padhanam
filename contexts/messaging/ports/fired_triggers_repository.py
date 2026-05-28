"""FiredTriggersRepository port — race-safe idempotency surface (D147, S54).

The HTTP trigger endpoint use case (FireTrigger at
``contexts/messaging/application/fire_trigger.py``) consults this
port before BROADCAST_INITIATED audit emission. The single method
``insert_or_skip`` returns True if the row was inserted (fresh
fire) or False if a row with the same
``(tenant_id, user_id, trigger_type, idempotency_key)`` already
existed (duplicate; skip dispatch).

Race-safety is provided at the persistence layer by the UNIQUE
constraint on the four-tuple — implementations use
``INSERT ... ON CONFLICT DO NOTHING`` per D147.

Tenant scoping flows through ``TenantContext``; cross-tenant writes
fail at the bound-tenant defence-in-depth per D24/D32. Ports layer
is pure per D16 — no SQLAlchemy, no vendor SDKs.
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel import TenantContext


class FiredTriggersRepository(Protocol):
    """Race-safe insert-or-skip surface for the fired_triggers table (D147)."""

    async def insert_or_skip(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        trigger_type: str,
        idempotency_key: str | None,
    ) -> bool:
        """Attempt to insert a fired_triggers row; return True if fresh.

        Implementations use ``INSERT ... ON CONFLICT DO NOTHING``
        keyed on the UNIQUE constraint
        ``(tenant_id, user_id, trigger_type, idempotency_key)``.
        A True return signals fresh-fire (the caller emits
        BROADCAST_INITIATED and invokes BroadcastDispatch). A False
        return signals duplicate (the caller logs structured
        "already fired" and exits without audit-chain or dispatch
        side effects).
        """
        ...


__all__ = ["FiredTriggersRepository"]
