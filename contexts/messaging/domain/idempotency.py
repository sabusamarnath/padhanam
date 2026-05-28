"""Idempotency key resolution per trigger type (D147, S54).

The HTTP trigger endpoint use case (FireTrigger) calls
``resolve_idempotency_key`` to compute the per-trigger-type
idempotency key it inserts into the fired_triggers table (D147). The
key is the third column of the UNIQUE constraint
``(tenant_id, user_id, trigger_type, idempotency_key)`` so its
semantics determine the idempotency window per trigger type:

- DAILY_SCHEDULED: the date string in the operator's configured
  timezone (one row per tenant+user+day) — a scheduler retry within
  the same day resolves to the same key and skips.
- MANUAL: ``None`` — manual triggers are not idempotency-protected;
  the UNIQUE constraint accommodates multiple null rows per Postgres
  semantics so every manual fire is fresh.
- THRESHOLD_CROSSED: raises ``NotImplementedError`` (S57 implements
  the composite-of-matched-event-plus-rule key).
- CALENDAR_EVENT, EMAIL_RECEIVED: raise ``NotImplementedError``
  (their metadata schemas commit at their Phase 2-B+ activation
  sessions per the deferred-decisions entry).

Per D16 domain code is framework-free — stdlib plus shared_kernel
only; the timezone conversion uses ``zoneinfo`` from stdlib.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from shared_kernel.broadcast_flow import BroadcastTriggerType


def _operator_today(operator_timezone: str, *, now: datetime | None = None) -> str:
    """Return the date string (YYYY-MM-DD) in the operator's timezone.

    ``now`` is injectable for deterministic testing; production passes
    the default (current UTC instant). An unknown timezone string
    raises ``ValueError`` so the endpoint surfaces a clear
    configuration error rather than silently defaulting.
    """
    instant = now or datetime.now(timezone.utc)
    try:
        tz = ZoneInfo(operator_timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(
            f"unknown operator_timezone {operator_timezone!r}; "
            "configure a valid IANA timezone name"
        ) from exc
    return instant.astimezone(tz).date().isoformat()


def resolve_idempotency_key(
    *,
    trigger_type: BroadcastTriggerType,
    metadata: dict[str, Any],
    operator_timezone: str,
    now: datetime | None = None,
) -> str | None:
    """Compute the idempotency key for the trigger type per D147.

    ``metadata`` is the TriggerContext.metadata open dict (Finding 3);
    DAILY_SCHEDULED ignores it (the key derives from the date),
    MANUAL returns ``None`` regardless. ``now`` is injectable for
    deterministic testing.

    Raises ``NotImplementedError`` for trigger types whose key
    semantics have not yet been committed (THRESHOLD_CROSSED at S57;
    CALENDAR_EVENT and EMAIL_RECEIVED at Phase 2-B+).
    """
    if trigger_type is BroadcastTriggerType.DAILY_SCHEDULED:
        return _operator_today(operator_timezone, now=now)
    if trigger_type is BroadcastTriggerType.MANUAL:
        return None
    raise NotImplementedError(
        f"idempotency key resolution for trigger_type="
        f"{trigger_type.value!r} is not committed yet; "
        "THRESHOLD_CROSSED lands at S57; CALENDAR_EVENT and "
        "EMAIL_RECEIVED land at their Phase 2-B+ activation sessions"
    )


__all__ = ["resolve_idempotency_key"]
