"""Register the manual entry cell with the ConversationFlow harness (S46).

S45 landed the contract harness with no implementers. S46's manual
entry cell is the first ConversationFlow implementer (D115); this
module registers it, and the five parametrised scenarios in
``test_conversation_flow_contract.py`` run against it.

The conftest globs ``test_*_conversation_flow.py`` to discover
registration modules, so this file's name carries the
``_conversation_flow`` suffix. ``make_instance`` builds the cell with
offline stubs: the structured-output stub returns an UnclearIntent
extraction so a harness ``turn`` runs without an LLM and never
touches the portfolio gateway (the stub gateway raises if called, so
an unexpected write surfaces loudly).
"""

from __future__ import annotations

from typing import Any

from contexts.audit.domain.events import AuditEvent
from contexts.messaging.application.manual_entry_cell import ManualEntryCell
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
    PendingClarificationStatus,
)
from shared_kernel import (
    ActorContext,
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
    """Returns a fixed UnclearIntent extraction — no LLM, no gateway call."""

    async def generate_structured(
        self, request: Any
    ) -> StructuredOutputResponse[dict[str, Any]]:
        return StructuredOutputResponse(
            value={
                "intent_type": "unclear",
                "clarification": "Could you say a little more?",
            },
            confidence=None,
            provider_metadata={},
        )


class _StubGateway:
    """A PortfolioGateway stub — the harness's UnclearIntent path never
    reaches it, so every method raises to surface an unexpected write."""

    async def find_cases(self, *, actor: ActorContext) -> Any:
        raise AssertionError("harness path must not read portfolio state")

    async def find_data_points(self, *, actor: ActorContext) -> Any:
        raise AssertionError("harness path must not read portfolio state")

    async def create_case(self, **_kwargs: Any) -> Any:
        raise AssertionError("harness path must not write portfolio state")

    async def create_data_point(self, **_kwargs: Any) -> Any:
        raise AssertionError("harness path must not write portfolio state")

    async def revise_data_point(self, **_kwargs: Any) -> Any:
        raise AssertionError("harness path must not write portfolio state")


def _harness_actor() -> ActorContext:
    tenant = TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a001",
    )
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=tenant,
        actor_id="conversation-flow-harness",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


class _StubConfidenceCalculator:
    """The harness's UnclearIntent path returns confidence None → default."""

    def compute(self, *, request: Any, response: Any) -> float:
        return 0.0


class _StubPendingRepo:
    """No-op pending repository — the UnclearIntent path never persists."""

    def __init__(self) -> None:
        self.pendings: dict[Any, PendingClarification] = {}

    async def save(self, *, tenant_context: Any, pending: Any) -> None:
        raise AssertionError("harness path must not persist a pending")

    async def update_status(self, *, tenant_context: Any, pending: Any) -> None:
        raise AssertionError("harness path must not transition a pending")

    async def get_by_id(self, *, tenant_context: Any, pending_id: Any) -> Any:
        return None

    async def get_active_for_user(
        self, *, tenant_context: Any, user_id: str
    ) -> Any:
        return None


class _StubPendingReader:
    """Returns no active pending — keeps the harness on the fresh-turn path."""

    async def get_active(self, *, tenant_id: Any, user_id: str) -> Any:
        return None


class _StubAuditPort:
    async def emit(self, event: AuditEvent) -> AuditEvent:
        return event


def _make_manual_entry_cell() -> ManualEntryCell:
    return ManualEntryCell(
        structured_output_port=_StubStructuredOutput(),
        portfolio_gateway=_StubGateway(),
        actor=_harness_actor(),
        confidence_calculator=_StubConfidenceCalculator(),
        pending_clarification_reader=_StubPendingReader(),
        pending_clarification_repository=_StubPendingRepo(),
        audit_port=_StubAuditPort(),
    )


register_conversation_flow_implementer(
    ConversationFlowImplementerFixture(
        name="manual_entry_cell",
        implementer_cls=ManualEntryCell,
        make_instance=_make_manual_entry_cell,
        sample_invocation=ConversationInvocation(
            purpose="manual_entry", actor_id="conversation-flow-harness"
        ),
        sample_input=ConversationInput(text="add a goal to the Q3 review"),
        sample_closure=ConversationClosure(reason="harness closed"),
    )
)
