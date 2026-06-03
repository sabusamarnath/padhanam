"""ThresholdEvaluator BroadcastFlow implementer (D142, D146, D153, S57).

The first stage of the proactive two-stage chain. Registered against the
BroadcastFlow registry under ``trigger_type=SCHEDULED_EVALUATION``; the
scheduled trigger (the deployment's scheduler hitting the HTTP trigger
endpoint) dispatches to it.

Its ``fire`` runs **refresh-then-evaluate** (D153):

1. Refresh the active-rule substrates through the consumer refresh port
   (calendar at Phase 2-A) so the state read is fresh — the proactivity
   property. A refresh that cannot complete is logged and the scan
   proceeds over the last-synced state (stale-but-present beats skipping).
2. Read the current calendar state through the consumer state-reader port
   (D153: evaluate over the state store, not the audit chain).
3. Evaluate the configured rules over the state (the two Phase 2-A
   must-haves: cancel + conflict).
4. For each match, emit ``THRESHOLD_CROSSED`` through the consumer emitter
   port (the D147 FireTrigger idempotency flow dedupes by crossing
   identity, so a crossing found on a later scan does not double-brief).
5. Return a ``ThresholdEvaluationResponse`` citing the matched meetings.

The evaluator holds only shared_kernel collaborators plus its four
consumer ports (refresh, state-reader, emitter, plus the configured
rules) — no producer-context imports, so the cross-context discipline
holds. It is a BroadcastFlow whose ``fire`` does not itself send a
user-facing message; the user-facing send is the second stage
(threshold-briefing). That two-stage shape is the deliberate cost of
reusing BroadcastDispatch for both the scan and the briefing (S57
reflection).

Application layer is framework-free here — stdlib plus shared_kernel plus
the threshold consumer ports.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from contexts.threshold_briefing.application.ports.active_rule_refresh import (
    ActiveRuleRefreshError,
    ActiveRuleRefreshPort,
)
from contexts.threshold_briefing.application.ports.calendar_state_reader import (
    CalendarStateReader,
)
from contexts.threshold_briefing.application.ports.threshold_crossed_emitter import (
    ThresholdCrossedEmitter,
)
from contexts.threshold_briefing.domain.evaluation import evaluate
from contexts.threshold_briefing.domain.response import (
    ThresholdEvaluationResponse,
    evaluation_response_for,
)
from contexts.threshold_briefing.domain.threshold_rule import ThresholdRule
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles
from shared_kernel.broadcast_flow import TriggerContext

_logger = logging.getLogger("padhanam.threshold_briefing.evaluator")


def _parse_triggered_at(triggered_at: str) -> datetime:
    """Parse the trigger's ISO timestamp; fall back to now() on malformed."""
    try:
        parsed = datetime.fromisoformat(triggered_at)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class ThresholdEvaluator:
    """The refresh-then-evaluate BroadcastFlow implementer (D153)."""

    def __init__(
        self,
        *,
        state_reader: CalendarStateReader,
        emitter: ThresholdCrossedEmitter,
        rules: tuple[ThresholdRule, ...],
        jurisdiction: str,
        refresh_port: ActiveRuleRefreshPort | None = None,
        scan_window_hours: int = 48,
    ) -> None:
        self._state_reader = state_reader
        self._emitter = emitter
        self._rules = rules
        self._jurisdiction = jurisdiction
        self._refresh_port = refresh_port
        self._scan_window_hours = scan_window_hours

    def _synthesise_actor(self, *, tenant_id: UUID, user_id: str) -> ActorContext:
        role_list = frozenset({ROLE_OPERATOR})
        return ActorContext(
            tenant_context=TenantContext(
                tenant_id=str(tenant_id),
                jurisdiction=self._jurisdiction,
                cost_attribution_id=str(tenant_id),
            ),
            actor_id=user_id,
            role_list=role_list,
            authorisation_set=authorisations_for_roles(role_list),
        )

    async def _maybe_refresh(self, *, actor: ActorContext) -> None:
        """Refresh active-rule substrates; log and proceed on failure (D153)."""
        if self._refresh_port is None:
            return
        try:
            await self._refresh_port.refresh(
                tenant_context=actor.tenant_context
            )
        except ActiveRuleRefreshError:
            _logger.warning(
                "active-rule refresh failed; evaluating over last-synced state",
                extra={"context": {"tenant_id": actor.tenant_context.tenant_id}},
            )

    async def fire(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        trigger_context: TriggerContext,
    ) -> ThresholdEvaluationResponse:
        """Refresh, evaluate over state, emit crossings, return the outcome (D153)."""
        actor = self._synthesise_actor(tenant_id=tenant_id, user_id=user_id)

        await self._maybe_refresh(actor=actor)

        window_end = _parse_triggered_at(trigger_context.triggered_at)
        window_start = window_end - timedelta(hours=self._scan_window_hours)

        meetings = await self._state_reader.list_meetings(
            actor=actor, include_cancelled=True
        )
        matches = evaluate(
            self._rules,
            meetings,
            window_start=window_start,
            window_end=window_end,
        )

        for match in matches:
            await self._emitter.emit(
                tenant_id=tenant_id,
                user_id=user_id,
                match=match,
                triggered_at=trigger_context.triggered_at,
            )

        return evaluation_response_for(matches)


__all__ = ["ThresholdEvaluator"]
