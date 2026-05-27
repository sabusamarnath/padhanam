"""Unit tests for mirror-conversation intent value objects (P14, S52)."""

from __future__ import annotations

import pytest

from contexts.mirror_conversation.domain.intent import (
    DrillDownToChild,
    ListCases,
    MirrorIntentType,
    ShowCase,
    ShowDataPoint,
    ShowParent,
    ShowSiblings,
    UnclearMirrorIntent,
    is_relative,
    mirror_intent_type_of,
    parse_mirror_intent,
)


def test_show_case_rejects_empty_reference() -> None:
    with pytest.raises(ValueError, match="case_reference"):
        ShowCase(case_reference="")


def test_show_data_point_rejects_empty_reference() -> None:
    with pytest.raises(ValueError, match="data_point_reference"):
        ShowDataPoint(data_point_reference="")


def test_drill_down_rejects_empty_reference() -> None:
    with pytest.raises(ValueError, match="child_reference"):
        DrillDownToChild(child_reference="")


def test_unclear_rejects_empty_clarification() -> None:
    with pytest.raises(ValueError, match="clarification"):
        UnclearMirrorIntent(clarification="")


def test_parse_show_case() -> None:
    raw = {
        "intent_class": "show_case",
        "case_reference": "Q3 portfolio review",
        "data_point_reference": "",
        "child_reference": "",
        "confidence": 0.95,
        "clarification": "",
    }
    intent = parse_mirror_intent(raw)
    assert isinstance(intent, ShowCase)
    assert intent.case_reference == "Q3 portfolio review"


def test_parse_list_cases() -> None:
    raw = {"intent_class": "list_cases", "confidence": 0.9}
    intent = parse_mirror_intent(raw)
    assert isinstance(intent, ListCases)


def test_parse_show_data_point_with_case_scope() -> None:
    raw = {
        "intent_class": "show_data_point",
        "data_point_reference": "revenue",
        "case_reference": "Q3 review",
        "child_reference": "",
        "confidence": 0.9,
        "clarification": "",
    }
    intent = parse_mirror_intent(raw)
    assert isinstance(intent, ShowDataPoint)
    assert intent.data_point_reference == "revenue"
    assert intent.case_reference == "Q3 review"


def test_parse_drill_down() -> None:
    raw = {
        "intent_class": "drill_down_to_child",
        "child_reference": "revenue",
        "confidence": 0.9,
    }
    intent = parse_mirror_intent(raw)
    assert isinstance(intent, DrillDownToChild)
    assert intent.child_reference == "revenue"


def test_parse_show_parent_and_siblings() -> None:
    parent = parse_mirror_intent({"intent_class": "show_parent"})
    siblings = parse_mirror_intent({"intent_class": "show_siblings"})
    assert isinstance(parent, ShowParent)
    assert isinstance(siblings, ShowSiblings)


def test_parse_unclear_with_clarification() -> None:
    raw = {
        "intent_class": "unclear_mirror",
        "clarification": "Which case do you mean?",
    }
    intent = parse_mirror_intent(raw)
    assert isinstance(intent, UnclearMirrorIntent)
    assert intent.clarification == "Which case do you mean?"


def test_parse_unclear_falls_back_when_required_field_missing() -> None:
    """Empty required field → UnclearMirrorIntent with a default clarification."""
    raw = {"intent_class": "show_case", "case_reference": ""}
    intent = parse_mirror_intent(raw)
    assert isinstance(intent, UnclearMirrorIntent)


def test_is_relative_classifies_correctly() -> None:
    assert is_relative(ShowParent())
    assert is_relative(ShowSiblings())
    assert is_relative(DrillDownToChild(child_reference="x"))
    assert not is_relative(ShowCase(case_reference="x"))
    assert not is_relative(ListCases())
    assert not is_relative(ShowDataPoint(data_point_reference="x"))


def test_mirror_intent_type_of_returns_canonical_strings() -> None:
    assert mirror_intent_type_of(ShowCase(case_reference="x")) == "show_case"
    assert mirror_intent_type_of(ListCases()) == "list_cases"
    assert (
        mirror_intent_type_of(ShowDataPoint(data_point_reference="x"))
        == "show_data_point"
    )
    assert (
        mirror_intent_type_of(DrillDownToChild(child_reference="x"))
        == "drill_down_to_child"
    )
    assert mirror_intent_type_of(ShowParent()) == "show_parent"
    assert mirror_intent_type_of(ShowSiblings()) == "show_siblings"
    assert (
        mirror_intent_type_of(UnclearMirrorIntent(clarification="x"))
        == "unclear_mirror"
    )
