"""Register the email-conversation cell with the ConversationFlow harness (D151, D152, S56b).

P15's email-conversation ConversationFlow implementer registers via this
module. The parametrised lifecycle scenarios in
``test_conversation_flow_contract.py`` plus the CitedResponse-conformance
and resolution-ambiguity-conformance scenarios run against it.

``make_instance`` builds the cell with offline stubs: the structured-
output stub returns an UnclearEmailIntent extraction so a harness
``turn`` runs without an LLM call. No refresh port is wired in the
harness build (refresh is exercised by the cell's own unit tests); the
harness path serves the cached store.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from contexts.email.domain.email import Email
from contexts.email_conversation.application.cell import (
    EmailConversationCell,
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

_TENANT = "00000000-0000-4000-8000-00000000a005"


class _StubStructuredOutput:
    def __init__(self, value: dict[str, Any] | None = None) -> None:
        self._value = value or {
            "intent_class": "unclear_email",
            "clarification": "Could you specify the email query?",
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


class _StubEmailReader:
    def __init__(self, emails: tuple[Email, ...] = ()) -> None:
        self._emails = emails

    async def get_by_message_id(
        self, *, tenant_context: Any, message_id: str
    ) -> Email | None:
        for e in self._emails:
            if e.message_id == message_id:
                return e
        return None

    async def list_emails(
        self, *, tenant_context: Any, include_deleted: bool = False
    ) -> tuple[Email, ...]:
        return self._emails

    async def list_live_message_ids_in_window(
        self, *, tenant_context: Any, window_start: datetime
    ) -> frozenset[str]:
        return frozenset(e.message_id for e in self._emails)


class _StubConfidenceCalculator:
    def compute(self, *, request: Any, response: Any) -> float:
        return float(getattr(response, "confidence", 0.0) or 0.0)


class _StubPendingRepo:
    def __init__(self) -> None:
        self.saved: list[Any] = []

    async def save(self, *, tenant_context: Any, pending: Any) -> None:
        self.saved.append(pending)

    async def update_status(self, *, tenant_context: Any, pending: Any) -> None:
        return None

    async def get_by_id(self, *, tenant_context: Any, pending_id: Any) -> Any:
        return None

    async def get_active_for_user(self, *, tenant_context: Any, user_id: str) -> Any:
        return None


class _StubPendingReader:
    async def get_active(self, *, tenant_id: Any, user_id: str) -> Any:
        return None


class _StubAuditPort:
    async def emit(self, event: Any) -> Any:
        return event


def _harness_actor() -> ActorContext:
    tenant = TenantContext(
        tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
    )
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=tenant,
        actor_id="email-conversation-harness",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _email(subject: str, *, message_id: str) -> Email:
    now = datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc)
    return Email(
        id=uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        message_id=message_id,
        thread_id="t1",
        from_address="sender@example.com",
        to_addresses=("me@example.com",),
        cc_addresses=(),
        subject=subject,
        body="body text",
        snippet="body text",
        received_at=now,
        labels=("INBOX",),
        history_id="9",
        content_hash="h",
        created_at=now,
        updated_at=now,
    )


def _make_email_conversation_cell(
    *,
    extraction: dict[str, Any] | None = None,
    emails: tuple[Email, ...] = (),
    pending_repo: _StubPendingRepo | None = None,
) -> EmailConversationCell:
    return EmailConversationCell(
        structured_output_port=_StubStructuredOutput(extraction),
        email_reader=_StubEmailReader(emails),
        actor=_harness_actor(),
        confidence_calculator=_StubConfidenceCalculator(),
        threshold_resolver=SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
        ),
        pending_clarification_reader=_StubPendingReader(),
        pending_clarification_repository=pending_repo or _StubPendingRepo(),
        audit_port=_StubAuditPort(),
        originating_intake_id=uuid4(),
        clock=lambda: datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc),
    )


register_conversation_flow_implementer(
    ConversationFlowImplementerFixture(
        name="email_conversation_cell",
        implementer_cls=EmailConversationCell,
        make_instance=_make_email_conversation_cell,
        sample_invocation=ConversationInvocation(
            purpose="email_query",
            actor_id="email-conversation-harness",
        ),
        sample_input=ConversationInput(text="what came in today?"),
        sample_closure=ConversationClosure(reason="harness closed"),
    )
)


def build_email_conversation_with_ambiguous_resolution() -> tuple[
    EmailConversationCell, _StubPendingRepo
]:
    """Build the cell in a subject-ambiguous condition for the D139 scenario."""
    repo = _StubPendingRepo()
    cell = _make_email_conversation_cell(
        extraction={
            "intent_class": "find_by_subject",
            "subject_reference": "Q3 portfolio review",
            "confidence": 0.95,
        },
        emails=(
            _email("Q3 portfolio review", message_id="msg-a"),
            _email("Q3 portfolio review", message_id="msg-b"),
        ),
        pending_repo=repo,
    )
    return cell, repo
