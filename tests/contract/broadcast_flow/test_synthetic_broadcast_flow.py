"""Register the synthetic harness BroadcastFlow implementer (S53).

S53 commits the BroadcastFlow contract harness without a real
user-facing implementer (daily-briefing lands at S54; threshold-
briefing plus ThresholdEvaluator at S57). This module registers a
synthetic implementer that satisfies the Protocol and returns a
minimal BroadcastResponse so the parametrised conformance scenarios
in ``test_broadcast_flow_conformance.py`` actually run at S53.

When real implementers land at S54+ they add their own
``test_<name>_broadcast_flow.py`` module and join the parametrised
set; this synthetic registration carries forward as a baseline harness
verifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from shared_kernel.broadcast_flow import (
    BroadcastResponse,
    BroadcastTriggerType,
    TriggerContext,
)
from shared_kernel.conversation_flow import ArtefactCitation

from tests.contract.broadcast_flow.conftest import (
    BroadcastFlowImplementerFixture,
    register_broadcast_flow_implementer,
)


@dataclass(frozen=True)
class _SyntheticBroadcastResponse:
    """A minimal value object satisfying BroadcastResponse structurally.

    Carries the three CitedResponse citation tuples (D138) plus a
    harness-only ``summary_text`` field demonstrating that per-
    implementer extension fields sit alongside the Protocol's load-
    bearing minimum.
    """

    cited_intake_records: tuple[UUID, ...]
    cited_audit_events: tuple[UUID, ...]
    cited_artefacts: tuple[ArtefactCitation, ...]
    summary_text: str


class SyntheticBroadcastFlow:
    """The S53 baseline BroadcastFlow harness implementer.

    Records every ``fire`` call so the parametrised scenarios can
    inspect the tenant_id / user_id pass-through plus the
    trigger_context shape. Per the brief Acceptance Criterion 4, the
    contract harness verifies (a) Protocol satisfaction (b) CitedResponse
    conformance (c) tenant-scoping at the fire boundary; this synthetic
    implementer is the harness fixture the scenarios run against until
    S54+ implementers register.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str, TriggerContext]] = []

    async def fire(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        trigger_context: TriggerContext,
    ) -> BroadcastResponse:
        self.calls.append((tenant_id, user_id, trigger_context))
        return _SyntheticBroadcastResponse(
            cited_intake_records=(),
            cited_audit_events=(),
            cited_artefacts=(),
            summary_text=(
                f"synthetic-fire {trigger_context.trigger_type.value} "
                f"for {user_id}"
            ),
        )


def _sample_trigger_context() -> TriggerContext:
    return TriggerContext(
        trigger_type=BroadcastTriggerType.MANUAL,
        trigger_id=uuid4(),
        triggered_at="2026-05-27T10:00:00+00:00",
    )


register_broadcast_flow_implementer(
    BroadcastFlowImplementerFixture(
        name="synthetic_broadcast_flow",
        implementer_cls=SyntheticBroadcastFlow,
        make_instance=SyntheticBroadcastFlow,
        handled_trigger_type=BroadcastTriggerType.MANUAL,
        sample_trigger_context_factory=_sample_trigger_context,
    )
)
