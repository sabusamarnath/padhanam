"""Register the daily-briefing BroadcastFlow implementer (D142, D146, S54).

S54 ships the first real BroadcastFlow implementer. This module
registers it against the contract harness with stub consumer ports
(reader / composer / notifier) so the parametrised conformance
scenarios in ``test_broadcast_flow_conformance.py`` run against the
daily-briefing implementer without a database — verifying the fire
signature, BroadcastFlow Protocol satisfaction, and DailyBriefingResponse
satisfying CitedResponse (D138).

The stub ports return representative data so the implementer composes a
real DailyBriefingResponse; the notifier stub records the send so the
harness confirms the implementer reached the outbound step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from contexts.daily_briefing.application.daily_briefing_implementer import (
    DailyBriefingImplementer,
)
from contexts.daily_briefing.application.ports.daily_briefing_composer import (
    DailyBriefingComposedContent,
)
from contexts.daily_briefing.application.ports.daily_briefing_reader import (
    DailyBriefingAuditEvent,
    DailyBriefingCase,
    DailyBriefingIntakeRecord,
)
from contexts.daily_briefing.domain.briefing_period import BriefingPeriod
from shared_kernel import ActorContext
from shared_kernel.broadcast_flow import BroadcastTriggerType, TriggerContext

from tests.contract.broadcast_flow.conftest import (
    BroadcastFlowImplementerFixture,
    register_broadcast_flow_implementer,
)


class _StubReader:
    async def read_intake_records(self, *, actor, window):  # noqa: ANN001
        return (
            DailyBriefingIntakeRecord(
                intake_id=uuid4(),
                intake_source="WHATSAPP_INBOUND",
                summary="a recent inbound",
                created_at=datetime(2026, 5, 28, 5, 0),
            ),
        )

    async def read_audit_events(self, *, actor, window):  # noqa: ANN001
        return (
            DailyBriefingAuditEvent(
                event_id=uuid4(),
                action_verb="portfolio.case.create",
                resource_type="case",
                resource_id=str(uuid4()),
                timestamp=datetime(2026, 5, 28, 5, 30),
            ),
        )

    async def read_active_cases(self, *, actor):  # noqa: ANN001
        return (
            DailyBriefingCase(
                case_id=uuid4(),
                title="Q3 portfolio review",
                status="OPEN",
                created_at=datetime(2026, 5, 1, 9, 0),
            ),
        )


class _StubComposer:
    async def compose(
        self,
        *,
        briefing_period: BriefingPeriod,
        intake_records,  # noqa: ANN001
        audit_events,  # noqa: ANN001
        active_cases,  # noqa: ANN001
    ) -> DailyBriefingComposedContent:
        return DailyBriefingComposedContent(
            prose_narrative="One new item; your portfolio stands at 1 case."
        )


@dataclass
class _StubNotifier:
    sent: list[str] = field(default_factory=list)

    async def send_briefing(self, *, actor: ActorContext, body: str) -> None:
        self.sent.append(body)


def _make_instance() -> DailyBriefingImplementer:
    return DailyBriefingImplementer(
        reader=_StubReader(),
        composer=_StubComposer(),
        notifier=_StubNotifier(),
        jurisdiction="eu-west",
        window_hours=24,
    )


def _sample_trigger_context() -> TriggerContext:
    return TriggerContext(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
        trigger_id=uuid4(),
        triggered_at="2026-05-28T06:00:00+00:00",
    )


register_broadcast_flow_implementer(
    BroadcastFlowImplementerFixture(
        name="daily_briefing",
        implementer_cls=DailyBriefingImplementer,
        make_instance=_make_instance,
        handled_trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
        sample_trigger_context_factory=_sample_trigger_context,
    )
)
