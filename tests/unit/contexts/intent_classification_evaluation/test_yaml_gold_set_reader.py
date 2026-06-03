"""Unit tests for the YAML gold-set reader (S48b, S51)."""

from __future__ import annotations

from pathlib import Path

import pytest

from contexts.intent_classification_evaluation.adapters.outbound.fixture.yaml_gold_set_reader import (
    YamlGoldSetReader,
)


_AUDIT_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures/intent_classification/audit_conversation_gold_set.yaml"
)
_MANUAL_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures/intent_classification/gold_set.yaml"
)
_META_CLASSIFIER_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures/intent_classification/meta_classifier_gold_set.yaml"
)
_MIRROR_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures/intent_classification/mirror_conversation_gold_set.yaml"
)
_CALENDAR_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures/intent_classification/calendar_conversation_gold_set.yaml"
)
_META_FOUR_WAY_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures/intent_classification/meta_classifier_four_way_gold_set.yaml"
)


def test_yaml_reader_loads_audit_conversation_fixture() -> None:
    reader = YamlGoldSetReader(path=_AUDIT_FIXTURE)
    gold_set = reader.get_gold_set("audit_conversation_p14_s51")
    assert gold_set.name == "audit_conversation_p14_s51"
    assert gold_set.intent_surface == "audit_conversation"
    assert len(gold_set.entries) >= 20
    # Sanity: at least one entry per audit-conversation intent class.
    classes = {e.expected_intent_class for e in gold_set.entries}
    assert "find_by_case" in classes
    assert "find_by_date_range" in classes
    assert "find_by_actor" in classes
    assert "find_by_event_type" in classes
    assert "find_by_combination" in classes
    assert "unclear_audit" in classes


def test_yaml_reader_loads_meta_classifier_fixture() -> None:
    """S52 commit 5: third instance of the parameterised D137 substrate."""
    reader = YamlGoldSetReader(path=_META_CLASSIFIER_FIXTURE)
    gold_set = reader.get_gold_set("meta_classifier_p14_s52")
    assert gold_set.name == "meta_classifier_p14_s52"
    assert gold_set.intent_surface == "dispatch_classifier"
    assert len(gold_set.entries) >= 20
    # Every entry's expected class names a real cell or the
    # dispatch_clarification sentinel.
    classes = {e.expected_intent_class for e in gold_set.entries}
    assert classes.issubset(
        {
            "manual_entry",
            "audit_conversation",
            "mirror_conversation",
            "dispatch_clarification",
        }
    )
    # Every real cell has at least one entry; the ambiguous bucket
    # carries best-guess identifiers per the gold-set's commentary.
    assert "manual_entry" in classes
    assert "audit_conversation" in classes
    assert "mirror_conversation" in classes


def test_yaml_reader_loads_mirror_conversation_fixture() -> None:
    """S52 commit 9: fourth instance of the parameterised D137 substrate.

    Entries with paired-turn ``prior_turns`` metadata load cleanly
    because the reader takes only ``input_phrasing`` plus
    ``expected_intent_class`` (and optional
    ``expected_confidence_minimum``); extra YAML keys are ignored.
    """
    reader = YamlGoldSetReader(path=_MIRROR_FIXTURE)
    gold_set = reader.get_gold_set("mirror_conversation_p14_s52")
    assert gold_set.name == "mirror_conversation_p14_s52"
    assert gold_set.intent_surface == "mirror_conversation"
    assert len(gold_set.entries) >= 25
    classes = {e.expected_intent_class for e in gold_set.entries}
    # Every mirror-conversation intent class has at least one entry.
    assert "show_case" in classes
    assert "list_cases" in classes
    assert "show_data_point" in classes
    assert "drill_down_to_child" in classes
    assert "show_parent" in classes
    assert "show_siblings" in classes
    assert "unclear_mirror" in classes


def test_yaml_reader_loads_calendar_conversation_fixture() -> None:
    """S55b-1: fifth instance of the parameterised D137 substrate."""
    reader = YamlGoldSetReader(path=_CALENDAR_FIXTURE)
    gold_set = reader.get_gold_set("calendar_conversation_p15_s55b1")
    assert gold_set.name == "calendar_conversation_p15_s55b1"
    assert gold_set.intent_surface == "calendar_conversation"
    assert len(gold_set.entries) >= 18
    classes = {e.expected_intent_class for e in gold_set.entries}
    # Every calendar-conversation intent class has at least one entry.
    assert "find_by_date_range" in classes
    assert "find_by_attendee" in classes
    assert "find_by_title" in classes
    assert "find_next_meeting" in classes
    assert "unclear_calendar" in classes


def test_yaml_reader_loads_meta_classifier_four_way_fixture() -> None:
    """S55b-2: the meta-classifier gold set extended to the fourth route."""
    reader = YamlGoldSetReader(path=_META_FOUR_WAY_FIXTURE)
    gold_set = reader.get_gold_set("meta_classifier_four_way_p15_s55b2")
    assert gold_set.name == "meta_classifier_four_way_p15_s55b2"
    assert gold_set.intent_surface == "dispatch_classifier"
    assert len(gold_set.entries) >= 20
    classes = {e.expected_intent_class for e in gold_set.entries}
    assert classes.issubset(
        {
            "manual_entry",
            "audit_conversation",
            "mirror_conversation",
            "calendar_conversation",
            "dispatch_clarification",
        }
    )
    # All four real surfaces carry at least one entry.
    assert "manual_entry" in classes
    assert "audit_conversation" in classes
    assert "mirror_conversation" in classes
    assert "calendar_conversation" in classes


def test_yaml_reader_loads_manual_entry_fixture_with_default_surface() -> None:
    if not _MANUAL_FIXTURE.exists():
        pytest.skip(
            "manual entry fixture not present in this checkout; "
            "skip is structurally honest."
        )
    reader = YamlGoldSetReader(path=_MANUAL_FIXTURE)
    # Read the YAML to discover the name, then load by name.
    import yaml as _yaml
    raw = _yaml.safe_load(_MANUAL_FIXTURE.read_text())
    name = raw["name"]
    gold_set = reader.get_gold_set(name)
    # Pre-S51 fixtures default to manual_entry per backward-compat.
    assert gold_set.intent_surface == "manual_entry"
