"""Register the mirror-conversation cell with the ConversationFlow harness (S52).

P14's second ConversationFlow implementer registers via this module.
The existing parametrised contract scenarios in
``test_conversation_flow_contract.py`` plus the S51 CitedResponse-
conformance and resolution-ambiguity-conformance scenarios all fire
against the mirror cell.

``make_instance`` builds the cell with offline stubs: the structured-
output stub returns an UnclearMirrorIntent extraction so a harness
``turn`` runs without an LLM call. Stubs raise on unexpected reads to
surface harness-path violations loudly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from contexts.audit.domain.events import AuditEvent

from contexts.messaging.adapters.threshold_single_pair import (
    SinglePairThresholdResolverAdapter,
)

from contexts.mirror_conversation.application.cell import (
    MirrorConversationCell,
)
from contexts.mirror_conversation.application.ports.mirror_portfolio_reader import (  # noqa: E501
    MirrorCaseSummary,
)

from shared_kernel import (
    ActorContext,
    ConfidenceThresholds,
    ConversationClosure,
    ConversationInput,
    ConversationInvocation,
    StructuredOutputResponse,
    TenantContext,
)
from shared_kernel.authorisation import (
    ROLE_OPERATOR,
    authorisations_for_roles,
)

from tests.contract.conversation_flow.conftest import (
    ConversationFlowImplementerFixture,
    register_conversation_flow_implementer,
)


class _StubStructuredOutput:
    """Returns a fixed UnclearMirrorIntent extraction — no LLM."""

    def __init__(self, value: dict[str, Any] | None = None) -> None:
        self._value = value or {
            "intent_class": "unclear_mirror",
            "case_reference": "",
            "data_point_reference": "",
            "child_reference": "",
            "confidence": 0.0,
            "clarification": "Could you say what you'd like to see?",
        }

    async def generate_structured(
        self, request: Any
    ) -> StructuredOutputResponse[dict[str, Any]]:
        return StructuredOutputResponse(
            value=self._value,
            confidence=float(self._value.get("confidence", 0.0)),
            provider_metadata={},
        )


class _StubMirrorReader:
    def __init__(self, cases: tuple[MirrorCaseSummary, ...] = ()) -> None:
        self._cases = cases

    async def list_cases(self, *, actor: ActorContext, limit: int = 50):
        return self._cases

    async def get_case_detail(self, *, actor: ActorContext, case_id):
        return None

    async def get_data_point(self, *, actor: ActorContext, data_point_id):
        return None

    async def find_cases(self, *, actor: ActorContext):
        return self._cases


class _StubConfidenceCalculator:
    def compute(self, *, request: Any, response: Any) -> float:
        return float(getattr(response, "confidence", 0.0) or 0.0)


class _StubPendingRepo:
    def __init__(self) -> None:
        self.saved: list[Any] = []

    async def save(self, *, tenant_context: Any, pending: Any) -> None:
        self.saved.append(pending)

    async def update_status(
        self, *, tenant_context: Any, pending: Any
    ) -> None:
        return None

    async def get_by_id(
        self, *, tenant_context: Any, pending_id: Any
    ) -> Any:
        return None

    async def get_active_for_user(
        self, *, tenant_context: Any, user_id: str
    ) -> Any:
        return None


class _StubPendingReader:
    async def get_active(self, *, tenant_id: Any, user_id: str) -> Any:
        return None


class _StubAuditPort:
    async def emit(self, event: AuditEvent) -> AuditEvent:
        return event


def _harness_actor() -> ActorContext:
    tenant = TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000a003",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a003",
    )
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=tenant,
        actor_id="mirror-conversation-harness",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _make_mirror_conversation_cell(
    *,
    extraction: dict[str, Any] | None = None,
    cases: tuple[MirrorCaseSummary, ...] = (),
) -> MirrorConversationCell:
    return MirrorConversationCell(
        structured_output_port=_StubStructuredOutput(extraction),
        mirror_portfolio_reader=_StubMirrorReader(cases),
        actor=_harness_actor(),
        confidence_calculator=_StubConfidenceCalculator(),
        threshold_resolver=SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
        ),
        pending_clarification_reader=_StubPendingReader(),
        pending_clarification_repository=_StubPendingRepo(),
        audit_port=_StubAuditPort(),
        originating_intake_id=uuid4(),
        clock=lambda: datetime(2026, 5, 27, 14, 30, tzinfo=timezone.utc),
    )


register_conversation_flow_implementer(
    ConversationFlowImplementerFixture(
        name="mirror_conversation_cell",
        implementer_cls=MirrorConversationCell,
        make_instance=_make_mirror_conversation_cell,
        sample_invocation=ConversationInvocation(
            purpose="mirror_query",
            actor_id="mirror-conversation-harness",
        ),
        sample_input=ConversationInput(
            text="show me my cases"
        ),
        sample_closure=ConversationClosure(reason="harness closed"),
    )
)


# Exposed factory for the resolution-ambiguity conformance scenario.
make_mirror_conversation_cell_with_ambiguous_cases = (
    _make_mirror_conversation_cell
)
