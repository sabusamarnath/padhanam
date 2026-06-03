"""Unit tests for email-conversation intent, query builder, and response (D151, S56b)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contexts.email_conversation.application.query_builder import (
    emails_from_sender,
    emails_in_window,
    recent_emails,
    resolve_subject_reference,
    resolve_window,
)
from contexts.email_conversation.application.response import (
    EmailConversationResponse,
    email_citation,
    render_for_whatsapp,
)
from contexts.email_conversation.domain.intent import (
    EmailIntentType,
    FindByDateRange,
    FindBySubject,
    FindFromSender,
    FindRecent,
    UnclearEmailIntent,
    email_intent_type_of,
    parse_email_intent,
)
from shared_kernel.conversation_flow import CitedResponse
from shared_kernel.intent_classification_email import EMAIL_INTENT_EXTRACTION_SCHEMA
from tests.unit.contexts.email_conversation.conftest import make_email

_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)  # Tuesday


# ---- intent ----

def test_parse_each_intent_class() -> None:
    assert parse_email_intent({"intent_class": "find_by_date_range", "range_keyword": "today"}) == FindByDateRange("today")
    assert parse_email_intent({"intent_class": "find_from_sender", "sender": "Ada"}) == FindFromSender("Ada")
    assert parse_email_intent({"intent_class": "find_by_subject", "subject_reference": "Q2"}) == FindBySubject("Q2")
    assert isinstance(parse_email_intent({"intent_class": "find_recent"}), FindRecent)
    assert isinstance(parse_email_intent({"intent_class": "unclear_email", "clarification": "?"}), UnclearEmailIntent)


def test_parse_coerces_unknown_and_missing_to_unclear() -> None:
    assert isinstance(parse_email_intent({}), UnclearEmailIntent)
    assert isinstance(parse_email_intent({"intent_class": "find_from_sender"}), UnclearEmailIntent)


def test_schema_enum_matches_intent_type() -> None:
    assert set(EMAIL_INTENT_EXTRACTION_SCHEMA["properties"]["intent_class"]["enum"]) == {
        t.value for t in EmailIntentType
    }


# ---- query builder ----

def test_window_and_sender_and_recent() -> None:
    e1 = make_email(subject="A", received_at=datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc), from_address="ada@x.com")
    e2 = make_email(subject="B", received_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc), from_address="bob@x.com")
    start, end = resolve_window("today", now=_NOW)
    assert {e.subject for e in emails_in_window((e1, e2), start=start, end=end)} == {"A"}
    assert {e.subject for e in emails_from_sender((e1, e2), sender="ADA")} == {"A"}
    # recent: newest first
    assert [e.subject for e in recent_emails((e2, e1), limit=10)] == ["A", "B"]


def test_resolve_subject_single_multi_none() -> None:
    a = make_email(subject="Quarterly board pack")
    b = make_email(subject="Quarterly board pack")
    c = make_email(subject="Lunch plans")
    matched, cands = resolve_subject_reference("lunch", (a, b, c))
    assert matched is c and cands == ()
    matched, cands = resolve_subject_reference("quarterly board pack", (a, b, c))
    assert matched is None and len(cands) == 2
    matched, cands = resolve_subject_reference("invoice xyz", (a, b, c))
    assert matched is None and cands == ()


# ---- response ----

def test_response_satisfies_cited_response_and_email_discriminator() -> None:
    r = EmailConversationResponse(text="x")
    assert isinstance(r, CitedResponse)
    cit = email_citation(uuid4())
    assert cit.artefact_type == "email"


def test_render_appends_citation_and_staleness() -> None:
    mid = uuid4()
    r = EmailConversationResponse(
        text="Emails today: 1 found.", cited_artefacts=(email_citation(mid),),
        staleness_note="Showing cached email; refresh timed out.",
    )
    out = render_for_whatsapp(r, composed_at=_NOW)
    assert "cached email" in out and f"email {mid.hex[:8]}" in out and "12:00 UTC" in out
