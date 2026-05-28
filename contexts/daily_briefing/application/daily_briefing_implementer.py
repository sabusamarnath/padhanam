"""Daily-briefing BroadcastFlow implementer (D142, D146, S54).

The first BroadcastFlow implementer. Registered against the BroadcastFlow
registry at composition root with ``trigger_type=DAILY_SCHEDULED``; the
HTTP trigger endpoint's FireTrigger use case (after the idempotency check
and BROADCAST_INITIATED audit emission) dispatches to it.

The ``fire`` method composes the response across five steps per D146:

1. Resolve the briefing window from the configured window-hours plus the
   trigger's ``triggered_at`` (the window ends at trigger time and looks
   back ``window_hours``).
2. Read recent IntakeRecords from the window via DailyBriefingReader.
3. Read recent audit events from the window via DailyBriefingReader.
4. Read active Cases via DailyBriefingReader.
5. Compose the prose via DailyBriefingComposer; construct the
   DailyBriefingResponse with citation tuples populated from the reads;
   render the channel body (D135); send via the BriefingNotifier; return
   the response.

The implementer synthesises the operator ActorContext from the fire's
``tenant_id`` plus ``user_id`` plus the configured jurisdiction — it
holds only shared_kernel collaborators plus its three consumer ports, so
the cross-context discipline holds (no producer-context imports).

Application layer is framework-free here — stdlib plus shared_kernel plus
the daily-briefing consumer ports.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from contexts.daily_briefing.application.ports.briefing_notifier import (
    BriefingNotifier,
)
from contexts.daily_briefing.application.ports.daily_briefing_composer import (
    DailyBriefingComposer,
)
from contexts.daily_briefing.application.ports.daily_briefing_reader import (
    DailyBriefingReader,
)
from contexts.daily_briefing.domain.briefing_period import BriefingPeriod
from contexts.daily_briefing.domain.response import (
    DailyBriefingResponse,
    render_for_whatsapp,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles
from shared_kernel.broadcast_flow import TriggerContext
from shared_kernel.conversation_flow import ArtefactCitation


def _parse_triggered_at(triggered_at: str) -> datetime:
    """Parse the trigger's ISO timestamp; fall back to now() on malformed."""
    try:
        parsed = datetime.fromisoformat(triggered_at)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class DailyBriefingImplementer:
    """The daily-briefing BroadcastFlow implementer (D142, D146)."""

    def __init__(
        self,
        *,
        reader: DailyBriefingReader,
        composer: DailyBriefingComposer,
        notifier: BriefingNotifier,
        jurisdiction: str,
        window_hours: int = 24,
    ) -> None:
        self._reader = reader
        self._composer = composer
        self._notifier = notifier
        self._jurisdiction = jurisdiction
        self._window_hours = window_hours

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

    async def fire(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        trigger_context: TriggerContext,
    ) -> DailyBriefingResponse:
        """Compose, render, send, and return the daily briefing (D146)."""
        actor = self._synthesise_actor(tenant_id=tenant_id, user_id=user_id)

        window_end = _parse_triggered_at(trigger_context.triggered_at)
        window_start = window_end - timedelta(hours=self._window_hours)
        period = BriefingPeriod(
            window_start=window_start, window_end=window_end
        )
        window = (window_start, window_end)

        intake_records = await self._reader.read_intake_records(
            actor=actor, window=window
        )
        audit_events = await self._reader.read_audit_events(
            actor=actor, window=window
        )
        active_cases = await self._reader.read_active_cases(actor=actor)

        content = await self._composer.compose(
            briefing_period=period,
            intake_records=intake_records,
            audit_events=audit_events,
            active_cases=active_cases,
        )

        response = DailyBriefingResponse(
            text=content.prose_narrative,
            briefing_period=period,
            cited_intake_records=tuple(r.intake_id for r in intake_records),
            cited_audit_events=tuple(e.event_id for e in audit_events),
            cited_artefacts=tuple(
                ArtefactCitation(artefact_id=c.case_id, artefact_type="case")
                for c in active_cases
            ),
        )

        body = render_for_whatsapp(
            response, composed_at=datetime.now(timezone.utc)
        )
        await self._notifier.send_briefing(actor=actor, body=body)
        return response


__all__ = ["DailyBriefingImplementer"]
