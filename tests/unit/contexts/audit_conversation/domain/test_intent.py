"""Unit tests for audit-conversation intent VOs and parse_audit_intent (S51)."""

from __future__ import annotations

from contexts.audit_conversation.domain.intent import (
    AuditIntentType,
    FindByActor,
    FindByCase,
    FindByCombination,
    FindByDateRange,
    FindByEventType,
    UnclearAuditIntent,
    audit_intent_type_of,
    parse_audit_intent,
)


def test_parse_find_by_case_intent() -> None:
    raw = {
        "intent_class": "find_by_case",
        "case_reference": "Q3 portfolio review",
    }
    intent = parse_audit_intent(raw)
    assert isinstance(intent, FindByCase)
    assert intent.case_reference == "Q3 portfolio review"
    assert audit_intent_type_of(intent) == AuditIntentType.FIND_BY_CASE.value


def test_parse_find_by_date_range_intent() -> None:
    raw = {"intent_class": "find_by_date_range", "range_keyword": "last_week"}
    intent = parse_audit_intent(raw)
    assert isinstance(intent, FindByDateRange)
    assert intent.range_keyword == "last_week"


def test_parse_find_by_actor_intent() -> None:
    raw = {"intent_class": "find_by_actor", "actor": "alice"}
    intent = parse_audit_intent(raw)
    assert isinstance(intent, FindByActor)
    assert intent.actor == "alice"


def test_parse_find_by_event_type_intent() -> None:
    raw = {
        "intent_class": "find_by_event_type",
        "event_type": "portfolio.case.create",
    }
    intent = parse_audit_intent(raw)
    assert isinstance(intent, FindByEventType)
    assert intent.event_type == "portfolio.case.create"


def test_parse_find_by_combination_intent() -> None:
    raw = {
        "intent_class": "find_by_combination",
        "case_reference": "Q3",
        "range_keyword": "this_week",
        "actor": "",
        "event_type": "",
    }
    intent = parse_audit_intent(raw)
    assert isinstance(intent, FindByCombination)
    assert intent.case_reference == "Q3"
    assert intent.range_keyword == "this_week"
    assert intent.actor is None
    assert intent.event_type is None


def test_parse_unclear_audit_intent() -> None:
    raw = {
        "intent_class": "unclear_audit",
        "clarification": "Could you clarify?",
    }
    intent = parse_audit_intent(raw)
    assert isinstance(intent, UnclearAuditIntent)
    assert intent.clarification == "Could you clarify?"


def test_parse_unknown_intent_class_returns_unclear() -> None:
    raw = {"intent_class": "frobnicate"}
    intent = parse_audit_intent(raw)
    assert isinstance(intent, UnclearAuditIntent)


def test_parse_missing_intent_class_returns_unclear() -> None:
    raw: dict[str, object] = {"case_reference": "Q3"}
    intent = parse_audit_intent(raw)
    assert isinstance(intent, UnclearAuditIntent)


def test_audit_intent_type_of_covers_all_variants() -> None:
    assert audit_intent_type_of(FindByCase(case_reference="x")) == "find_by_case"
    assert (
        audit_intent_type_of(FindByDateRange(range_keyword="today"))
        == "find_by_date_range"
    )
    assert audit_intent_type_of(FindByActor(actor="alice")) == "find_by_actor"
    assert (
        audit_intent_type_of(FindByEventType(event_type="e"))
        == "find_by_event_type"
    )
    assert (
        audit_intent_type_of(FindByCombination())
        == "find_by_combination"
    )
    assert (
        audit_intent_type_of(UnclearAuditIntent(clarification=""))
        == "unclear_audit"
    )
