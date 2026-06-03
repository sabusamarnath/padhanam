"""Unit tests for email-conversation refresh-before-answer (D152 Option A, S56b)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from contexts.email_conversation.application.cell import EmailConversationCell
from contexts.email_conversation.application.ports.email_refresh import EmailRefreshError
from contexts.messaging.adapters.threshold_single_pair import (
    SinglePairThresholdResolverAdapter,
)
from shared_kernel import ConfidenceThresholds, ConversationInput, ConversationInvocation
from tests.unit.contexts.email_conversation.conftest import make_email
from tests.unit.contexts.email_conversation.test_cell import (
    _FakeEmailReader,
    _PendingStore,
    _StubAudit,
    _StubConfidence,
    _StubStructuredOutput,
    _actor,
)

_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)


class _RefreshOk:
    def __init__(self) -> None:
        self.calls = 0

    async def refresh(self, *, tenant_context: Any) -> None:
        self.calls += 1


class _RefreshSlow:
    async def refresh(self, *, tenant_context: Any) -> None:
        await asyncio.sleep(1.0)


class _RefreshFails:
    async def refresh(self, *, tenant_context: Any) -> None:
        raise EmailRefreshError("nango unreachable")


def _cell(refresh_port, *, timeout: float = 0.05):
    e = make_email(subject="Board pack", received_at=datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc))
    return EmailConversationCell(
        structured_output_port=_StubStructuredOutput(
            {"intent_class": "find_by_date_range", "range_keyword": "today", "confidence": 0.95}
        ),
        email_reader=_FakeEmailReader((e,)),
        actor=_actor(),
        confidence_calculator=_StubConfidence(),
        threshold_resolver=SinglePairThresholdResolverAdapter(thresholds=ConfidenceThresholds(high=0.8, medium=0.5)),
        pending_clarification_reader=_PendingStore(),
        pending_clarification_repository=_PendingStore(),
        audit_port=_StubAudit(),
        refresh_port=refresh_port,
        refresh_timeout_seconds=timeout,
        originating_intake_id=uuid4(),
        clock=lambda: _NOW,
    )


def _turn(cell):
    async def _drive():
        st = await cell.open(ConversationInvocation(purpose="email_query", actor_id="email-harness"))
        return await cell.turn(st, ConversationInput(text="what came in today?"))
    return asyncio.run(_drive())


def test_refresh_succeeds_then_answers_without_note() -> None:
    refresh = _RefreshOk()
    resp = _turn(_cell(refresh)).payload["email_response"]
    assert refresh.calls == 1 and resp.staleness_note is None and resp.cited_artefacts


def test_refresh_times_out_falls_back_with_note() -> None:
    resp = _turn(_cell(_RefreshSlow())).payload["email_response"]
    assert resp.staleness_note is not None and "timed out" in resp.staleness_note and resp.cited_artefacts


def test_refresh_fails_falls_back_with_note() -> None:
    resp = _turn(_cell(_RefreshFails())).payload["email_response"]
    assert resp.staleness_note is not None and "unavailable" in resp.staleness_note and resp.cited_artefacts
