"""ThresholdCrossedEmitter consumer port (D147, D153, S57).

The evaluator's emit surface: on a rule match it emits a
``THRESHOLD_CROSSED`` trigger that routes to the threshold-briefing
implementer. Per D16/D17 the threshold context cannot import
``contexts.messaging.application`` (FireTrigger) directly, so it consumes
this consumer-defined port; the ``apps/`` wiring adapter implements it by
constructing the THRESHOLD_CROSSED ``TriggerContext`` (carrying the
crossing metadata via ``RuleMatch.to_trigger_metadata``) and invoking the
D147 FireTrigger flow — which resolves the idempotency key from the
crossing identity, inserts the fired_triggers row (one brief per
crossing), emits BROADCAST_INITIATED, and dispatches to threshold-briefing.

Framework-free per D16 — stdlib plus shared_kernel only.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from contexts.threshold_briefing.domain.rule_match import RuleMatch


class ThresholdCrossedEmitter(Protocol):
    """Emit a THRESHOLD_CROSSED trigger for a crossing (D147, D153)."""

    async def emit(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        match: RuleMatch,
        triggered_at: str,
    ) -> None:
        """Emit THRESHOLD_CROSSED for ``match`` through the FireTrigger flow.

        The implementation builds the TriggerContext from the match's
        ``to_trigger_metadata`` and fires it idempotently (the crossing
        identity seeds the idempotency key, so the same crossing found on
        a later scan does not double-brief).
        """
        ...


__all__ = ["ThresholdCrossedEmitter"]
