"""Unit tests for the manual entry cell's intent value objects (S46)."""

from __future__ import annotations

import pytest

from contexts.messaging.domain.intent import (
    INTENT_EXTRACTION_SCHEMA,
    AddDataPointIntent,
    CreateCaseIntent,
    IntentType,
    ReviseDataPointIntent,
    UnclearIntent,
    parse_intent,
)


def test_create_case_intent_requires_non_empty_title() -> None:
    assert CreateCaseIntent(title="Q3 portfolio review").title == (
        "Q3 portfolio review"
    )
    with pytest.raises(ValueError, match="title must be non-empty"):
        CreateCaseIntent(title="   ")


def test_add_data_point_intent_validates_data_point_type() -> None:
    intent = AddDataPointIntent(
        case_reference="the Q3 review case",
        data_point_type="GOAL",
        value_text="ship Wave 1 by end of May",
    )
    assert intent.data_point_type == "GOAL"
    with pytest.raises(ValueError, match="data_point_type must be one of"):
        AddDataPointIntent(
            case_reference="the Q3 review case",
            data_point_type="NOTE",
            value_text="something",
        )


def test_add_data_point_intent_requires_non_empty_fields() -> None:
    with pytest.raises(ValueError, match="case_reference must be non-empty"):
        AddDataPointIntent(
            case_reference="",
            data_point_type="STATUS",
            value_text="on track",
        )
    with pytest.raises(ValueError, match="value_text must be non-empty"):
        AddDataPointIntent(
            case_reference="the case",
            data_point_type="STATUS",
            value_text="  ",
        )


def test_revise_data_point_intent_requires_non_empty_fields() -> None:
    intent = ReviseDataPointIntent(
        data_point_reference="the Wave 1 goal",
        value_text="ship Wave 1 by mid-June",
    )
    assert intent.value_text == "ship Wave 1 by mid-June"
    with pytest.raises(ValueError, match="data_point_reference must be"):
        ReviseDataPointIntent(data_point_reference="", value_text="x")


def test_unclear_intent_requires_non_empty_clarification() -> None:
    assert UnclearIntent(clarification="What case?").clarification == (
        "What case?"
    )
    with pytest.raises(ValueError, match="clarification must be non-empty"):
        UnclearIntent(clarification="")


def test_parse_intent_create_case() -> None:
    intent = parse_intent(
        {
            "intent_type": "create_case",
            "title": "Q3 portfolio review",
            "case_reference": "",
            "data_point_type": "",
            "data_point_reference": "",
            "value_text": "",
            "clarification": "",
        }
    )
    assert intent == CreateCaseIntent(title="Q3 portfolio review")


def test_parse_intent_add_data_point() -> None:
    intent = parse_intent(
        {
            "intent_type": "add_data_point",
            "title": "",
            "case_reference": "the Q3 review",
            "data_point_type": "GOAL",
            "data_point_reference": "",
            "value_text": "ship Wave 1",
            "clarification": "",
        }
    )
    assert intent == AddDataPointIntent(
        case_reference="the Q3 review",
        data_point_type="GOAL",
        value_text="ship Wave 1",
    )


def test_parse_intent_revise_data_point() -> None:
    intent = parse_intent(
        {
            "intent_type": "revise_data_point",
            "title": "",
            "case_reference": "",
            "data_point_type": "",
            "data_point_reference": "the Wave 1 goal",
            "value_text": "ship Wave 1 by mid-June",
            "clarification": "",
        }
    )
    assert intent == ReviseDataPointIntent(
        data_point_reference="the Wave 1 goal",
        value_text="ship Wave 1 by mid-June",
    )


def test_parse_intent_unclear_uses_supplied_clarification() -> None:
    intent = parse_intent(
        {"intent_type": "unclear", "clarification": "Which case did you mean?"}
    )
    assert intent == UnclearIntent(clarification="Which case did you mean?")


def test_parse_intent_coerces_degraded_extraction_to_unclear() -> None:
    # create_case with an empty title cannot construct CreateCaseIntent;
    # the result coerces to UnclearIntent rather than raising.
    intent = parse_intent(
        {"intent_type": "create_case", "title": "", "clarification": ""}
    )
    assert isinstance(intent, UnclearIntent)
    assert intent.clarification  # the default clarification is non-empty


def test_parse_intent_unknown_type_coerces_to_unclear() -> None:
    intent = parse_intent({"intent_type": "drop_case", "clarification": ""})
    assert isinstance(intent, UnclearIntent)


def test_intent_extraction_schema_is_strict_mode_shaped() -> None:
    assert INTENT_EXTRACTION_SCHEMA["additionalProperties"] is False
    # Strict mode requires every property in ``required``.
    assert set(INTENT_EXTRACTION_SCHEMA["required"]) == set(
        INTENT_EXTRACTION_SCHEMA["properties"]
    )
    assert INTENT_EXTRACTION_SCHEMA["properties"]["intent_type"]["enum"] == [
        t.value for t in IntentType
    ]
