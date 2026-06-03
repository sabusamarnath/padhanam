"""Unit tests for the email-conversation cell (D138, D139, D151, S56b)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from contexts.email_conversation.application.cell import EmailConversationCell
from contexts.messaging.adapters.threshold_single_pair import (
    SinglePairThresholdResolverAdapter,
)
from shared_kernel import (
    ActorContext,
    ConfidenceThresholds,
    ConversationInput,
    ConversationInvocation,
    StructuredOutputParseFailure,
    StructuredOutputResponse,
    TenantContext,
)
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles
from tests.unit.contexts.email_conversation.conftest import make_email

_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
_TENANT = "00000000-0000-4000-8000-00000000a001"


class _StubStructuredOutput:
    def __init__(self, value: dict[str, Any], *, raise_parse: bool = False) -> None:
        self._value = value
        self._raise = raise_parse

    async def generate_structured(self, request: Any) -> Any:
        if self._raise:
            raise StructuredOutputParseFailure("bad")
        return StructuredOutputResponse(
            value=self._value, confidence=float(self._value.get("confidence", 0.0)), provider_metadata={}
        )


class _StubConfidence:
    def compute(self, *, request: Any, response: Any) -> float:
        return float(getattr(response, "confidence", 0.0) or 0.0)


class _FakeEmailReader:
    def __init__(self, emails: tuple) -> None:
        self._emails = emails

    async def list_emails(self, *, tenant_context: Any, include_deleted: bool = False):
        return self._emails

    async def get_by_message_id(self, *, tenant_context: Any, message_id: str):
        for e in self._emails:
            if e.message_id == message_id:
                return e
        return None


class _PendingStore:
    def __init__(self) -> None:
        self.saved: list[Any] = []
        self._active: Any = None

    async def save(self, *, tenant_context: Any, pending: Any) -> None:
        self.saved.append(pending); self._active = pending

    async def update_status(self, *, tenant_context: Any, pending: Any) -> None:
        self._active = None

    async def get_by_id(self, **k: Any) -> Any:
        return None

    async def get_active_for_user(self, **k: Any) -> Any:
        return self._active

    async def get_active(self, *, tenant_id: Any, user_id: str) -> Any:
        return self._active


class _StubAudit:
    async def emit(self, e: Any) -> Any:
        return e


def _actor() -> ActorContext:
    tenant = TenantContext(tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT)
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(tenant_context=tenant, actor_id="email-harness", role_list=roles, authorisation_set=authorisations_for_roles(roles))


def _cell(value: dict, *, emails: tuple = (), raise_parse: bool = False, store: _PendingStore | None = None):
    store = store or _PendingStore()
    cell = EmailConversationCell(
        structured_output_port=_StubStructuredOutput(value, raise_parse=raise_parse),
        email_reader=_FakeEmailReader(emails),
        actor=_actor(),
        confidence_calculator=_StubConfidence(),
        threshold_resolver=SinglePairThresholdResolverAdapter(thresholds=ConfidenceThresholds(high=0.8, medium=0.5)),
        pending_clarification_reader=store,
        pending_clarification_repository=store,
        audit_port=_StubAudit(),
        originating_intake_id=uuid4(),
        clock=lambda: _NOW,
    )
    return cell, store


def _turn(cell, text: str):
    async def _drive():
        st = await cell.open(ConversationInvocation(purpose="email_query", actor_id="email-harness"))
        return await cell.turn(st, ConversationInput(text=text))
    return asyncio.run(_drive())


def test_find_by_date_range_cites_emails() -> None:
    e = make_email(subject="Board pack", received_at=datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc))
    cell, _ = _cell({"intent_class": "find_by_date_range", "range_keyword": "today", "confidence": 0.95}, emails=(e,))
    resp = _turn(cell, "what came in today?").payload["email_response"]
    assert resp.cited_artefacts and resp.cited_artefacts[0].artefact_type == "email"


def test_find_from_sender() -> None:
    e = make_email(subject="Re: deal", from_address="ada@x.com", received_at=_NOW)
    cell, _ = _cell({"intent_class": "find_from_sender", "sender": "ada", "confidence": 0.95}, emails=(e,))
    assert len(_turn(cell, "email from ada").payload["email_response"].cited_artefacts) == 1


def test_find_recent() -> None:
    e = make_email(subject="latest", received_at=_NOW)
    cell, _ = _cell({"intent_class": "find_recent", "confidence": 0.95}, emails=(e,))
    assert _turn(cell, "what's new").payload["email_response"].cited_artefacts


def test_find_by_subject_single() -> None:
    e = make_email(subject="Quarterly business review", received_at=_NOW)
    cell, _ = _cell({"intent_class": "find_by_subject", "subject_reference": "quarterly business review", "confidence": 0.95}, emails=(e,))
    assert len(_turn(cell, "the QBR email").payload["email_response"].cited_artefacts) == 1


def test_medium_confidence_persists_pending() -> None:
    cell, store = _cell({"intent_class": "find_recent", "confidence": 0.6})
    st = _turn(cell, "recent?")
    assert st.payload["confidence_band"] == "medium" and len(store.saved) == 1


def test_unclear_and_parse_failure() -> None:
    cell, _ = _cell({"intent_class": "unclear_email", "clarification": "What would you like?", "confidence": 0.9})
    assert _turn(cell, "send a reply to bob").payload["confidence_band"] == "low"
    cell2, _ = _cell({}, raise_parse=True)
    assert _turn(cell2, "???").payload["confidence_band"] == "parse_failure"


def test_resolution_ambiguity_and_positional_selection() -> None:
    a = make_email(subject="Project Falcon", message_id="m-a", received_at=_NOW)
    b = make_email(subject="Project Falcon", message_id="m-b", received_at=_NOW)
    cell, store = _cell({"intent_class": "find_by_subject", "subject_reference": "project falcon", "confidence": 0.95}, emails=(a, b))

    async def _drive():
        st = await cell.open(ConversationInvocation(purpose="email_query", actor_id="email-harness"))
        st = await cell.turn(st, ConversationInput(text="the project falcon email"))
        assert st.payload["confidence_band"] == "resolution_ambiguous"
        assert len(store.saved[0].proposed_intent["resolution_candidates"]) == 2
        return await cell.turn(st, ConversationInput(text="1"))

    final = asyncio.run(_drive())
    assert final.payload["confidence_band"] == "resolution_selected"
    assert len(final.payload["email_response"].cited_artefacts) == 1
