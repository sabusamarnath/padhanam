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
