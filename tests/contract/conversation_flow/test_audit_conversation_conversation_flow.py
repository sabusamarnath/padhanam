"""Register the audit-conversation cell with the ConversationFlow harness (S51).

P14's audit-conversation ConversationFlow implementer registers via this
module. The five existing parametrised scenarios in
``test_conversation_flow_contract.py`` run against it; the two new
CitedResponse-conformance and resolution-ambiguity-conformance scenarios
added at S51 commit 5 also run against it.

The conftest globs ``test_*_conversation_flow.py`` to discover
registration modules; this file's name carries the
``_conversation_flow`` suffix per the convention.

``make_instance`` builds the cell with offline stubs: the structured-
output stub returns an UnclearAuditIntent extraction so a harness
``turn`` runs without an LLM call. Stubs raise on unexpected reads to
surface harness-path-violations loudly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from contexts.audit.domain.chain_integrity import ChainIntegrityVerification
from contexts.audit.domain.events import AuditEvent
from contexts.audit.domain.query_filters import AuditEventListPage

from contexts.audit_conversation.application.cell import (
    AuditConversationCell,
)
from contexts.audit_conversation.application.ports.portfolio_case_lookup import (
    AuditCaseSummary,
)

from contexts.messaging.adapters.threshold_single_pair import (
    SinglePairThresholdResolverAdapter,
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
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

from tests.contract.conversation_flow.conftest import (
    ConversationFlowImplementerFixture,
    register_conversation_flow_implementer,
)


class _StubStructuredOutput:
    """Returns a fixed UnclearAuditIntent extraction — no LLM, no audit read."""

    def __init__(self, value: dict[str, Any] | None = None) -> None:
        self._value = value or {
            "intent_class": "unclear_audit",
            "clarification": "Could you specify the audit query?",
            "confidence": 0.0,
        }

    async def generate_structured(
        self, request: Any
    ) -> StructuredOutputResponse[dict[str, Any]]:
        return StructuredOutputResponse(
            value=self._value,
            confidence=float(self._value.get("confidence", 0.0)),
            provider_metadata={},
        )


class _StubAuditReader:
    """The harness's UnclearAuditIntent path never reaches it."""

    def __init__(self, events: tuple[Any, ...] = ()) -> None:
        self._events = events

    async def get_audit_event(self, **kwargs: Any) -> Any:
        raise AssertionError("harness path must not read audit events")

    async def list_audit_events_with_filters(self, **kwargs: Any) -> Any:
        return AuditEventListPage(
            events=self._events,
            next_cursor=None,
            chain_integrity=ChainIntegrityVerification(status="verified"),
        )

    async def verify_chain_segment(self, **kwargs: Any) -> Any:
        return ChainIntegrityVerification(status="verified")


class _StubCaseLookup:
    """Portfolio-case-lookup stub returning a fixed case list."""

    def __init__(self, cases: tuple[AuditCaseSummary, ...] = ()) -> None:
        self._cases = cases

    async def find_cases(self, *, actor: ActorContext) -> Any:
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
        tenant_id="00000000-0000-4000-8000-00000000a002",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a002",
    )
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=tenant,
        actor_id="audit-conversation-harness",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _make_audit_conversation_cell(
    *,
    extraction: dict[str, Any] | None = None,
    cases: tuple[AuditCaseSummary, ...] = (),
) -> AuditConversationCell:
    return AuditConversationCell(
        structured_output_port=_StubStructuredOutput(extraction),
        audit_event_reader=_StubAuditReader(),
        portfolio_case_lookup=_StubCaseLookup(cases),
        actor=_harness_actor(),
        confidence_calculator=_StubConfidenceCalculator(),
        threshold_resolver=SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
        ),
        pending_clarification_reader=_StubPendingReader(),
        pending_clarification_repository=_StubPendingRepo(),
        audit_port=_StubAuditPort(),
        originating_intake_id=uuid4(),
        clock=lambda: datetime(2026, 5, 26, 14, 30, tzinfo=timezone.utc),
    )


register_conversation_flow_implementer(
    ConversationFlowImplementerFixture(
        name="audit_conversation_cell",
        implementer_cls=AuditConversationCell,
        make_instance=_make_audit_conversation_cell,
        sample_invocation=ConversationInvocation(
            purpose="audit_query",
            actor_id="audit-conversation-harness",
        ),
        sample_input=ConversationInput(
            text="show audit events for today"
        ),
        sample_closure=ConversationClosure(reason="harness closed"),
    )
)


# Exposed factory for the resolution-ambiguity conformance scenario
# (the scenario builds an audit-conversation cell with multi-match
# cases to exercise the D139 routing).
make_audit_conversation_cell_with_ambiguous_cases = (
    _make_audit_conversation_cell
)
