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
- SCHEDULED_EVALUATION: ``None`` (S57) — the threshold-evaluator scan
  is not idempotency-protected; it runs on every cadence tick (a
  per-day or per-hour key would suppress later scans). Dedup happens
  one stage downstream, at the THRESHOLD_CROSSED key, so the same
  crossing found on successive scans does not double-brief.
- THRESHOLD_CROSSED: the crossing's derived-state identity (S57, D153)
  — ``metadata["crossing_identity"]`` (rule_id + event + cancelled_at,
  or rule_id + the unordered conflict pair). One brief per crossing,
  no double-fire across scans.
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
    if trigger_type is BroadcastTriggerType.SCHEDULED_EVALUATION:
        # Not idempotency-protected: the scan runs every cadence tick;
        # dedup is the downstream THRESHOLD_CROSSED key (D153).
        return None
    if trigger_type is BroadcastTriggerType.THRESHOLD_CROSSED:
        return _threshold_crossed_key(metadata)
    raise NotImplementedError(
        f"idempotency key resolution for trigger_type="
        f"{trigger_type.value!r} is not committed yet; "
        "CALENDAR_EVENT and EMAIL_RECEIVED land at their Phase 2-B+ "
        "activation sessions"
    )


def _threshold_crossed_key(metadata: dict[str, Any]) -> str:
    """Derived-state idempotency key for a THRESHOLD_CROSSED crossing (D153).

    Prefers the ``crossing_identity`` the evaluator placed on the
    metadata (rule_id + event + cancelled_at, or rule_id + sorted
    conflict pair). Falls back to a composite of the rule and event ids
    when ``crossing_identity`` is absent, so a malformed metadata still
    dedupes deterministically rather than every fire being fresh.
    """
    identity = str(metadata.get("crossing_identity", "")).strip()
    if identity:
        return identity
    rule_id = str(metadata.get("rule_id", "")).strip()
    google_event_id = str(metadata.get("google_event_id", "")).strip()
    cancelled_at = str(metadata.get("cancelled_at", "")).strip()
    return f"{rule_id}:{google_event_id}:{cancelled_at}"


__all__ = ["resolve_idempotency_key"]
