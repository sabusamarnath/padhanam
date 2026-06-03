"""ThresholdBriefingImplementer BroadcastFlow implementer (D142, D146, D153, S57).

The second stage of the proactive two-stage chain. Registered against the
BroadcastFlow registry under ``trigger_type=THRESHOLD_CROSSED``; the
evaluator's emitted crossing (routed through the D147 FireTrigger
idempotency flow) dispatches to it.

Its ``fire``:

1. Read the crossing from the trigger metadata (the emitter placed it
   there via ``RuleMatch.to_trigger_metadata``) — the briefing never
   re-reads the calendar store, so it is decoupled from the state the
   evaluator read.
2. Compose the proactive prose via the consumer composer port; on a
   composer failure, fall back to the crossing's own summary (a proactive
   surface must still surface the heads-up even if the LLM is down).
3. Construct the ThresholdBriefingResponse (citing the affected meeting),
   render to WhatsApp (D135), send via the consumer notifier port, return.

Holds only shared_kernel collaborators plus its two consumer ports — no
producer-context imports. Application layer is framework-free here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from contexts.threshold_briefing.application.ports.threshold_briefing_composer import (
    ThresholdBriefingComposer,
)
from contexts.threshold_briefing.application.ports.threshold_notifier import (
    ThresholdNotifier,
)
from contexts.threshold_briefing.domain.crossing import ThresholdCrossing
from contexts.threshold_briefing.domain.response import (
    ThresholdBriefingResponse,
    briefing_response_for,
    render_for_whatsapp,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles
from shared_kernel.broadcast_flow import TriggerContext

_logger = logging.getLogger("padhanam.threshold_briefing.briefing")


class ThresholdBriefingImplementer:
    """The threshold-briefing BroadcastFlow implementer (D142, D153)."""

    def __init__(
        self,
        *,
        composer: ThresholdBriefingComposer,
        notifier: ThresholdNotifier,
        jurisdiction: str,
    ) -> None:
        self._composer = composer
        self._notifier = notifier
        self._jurisdiction = jurisdiction

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

    async def _compose(self, *, crossing: ThresholdCrossing) -> str:
        """Compose prose; fall back to the crossing summary on composer failure."""
        try:
            prose = await self._composer.compose(crossing=crossing)
        except Exception:
            _logger.warning(
                "threshold-briefing composer failed; using crossing summary",
                extra={"context": {"crossing_identity": crossing.crossing_identity}},
            )
            return crossing.summary
        return prose or crossing.summary

    async def fire(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        trigger_context: TriggerContext,
    ) -> ThresholdBriefingResponse:
        """Compose, render, send, and return the threshold briefing (D153)."""
        actor = self._synthesise_actor(tenant_id=tenant_id, user_id=user_id)
        crossing = ThresholdCrossing.from_metadata(trigger_context.metadata)

        prose = await self._compose(crossing=crossing)
        response = briefing_response_for(text=prose, crossing=crossing)

        body = render_for_whatsapp(response, composed_at=datetime.now(timezone.utc))
        await self._notifier.send_briefing(actor=actor, body=body)
        return response


__all__ = ["ThresholdBriefingImplementer"]
