"""YAML-backed GoldSetReader adapter for the intent-classification substrate (D137, S48b).

Reads gold sets from a YAML file at a configured path. Each YAML
document carries:

```yaml
name: phase_2_a_default
entries:
  - input_phrasing: "Create a case for the Q3 review"
    expected_intent_class: create_case
  - input_phrasing: "Add a goal to the Q3 review: ship Wave 1"
    expected_intent_class: add_data_point
    expected_confidence_minimum: 0.5
  ...
```

The reader is constructed with a path; ``get_gold_set(name)`` loads
the YAML and returns the matching ``IntentClassificationGoldSet``.
The fixture-loader path supports the Phase 2-A operator-dogfooding
shape; per-tenant gold-set authoring (D137 alternative (c)) swaps
in a Postgres-backed adapter without runner-side change.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from contexts.intent_classification_evaluation.domain.gold_set import (
    IntentClassificationGoldSet,
    IntentClassificationGoldSetEntry,
)


class YamlGoldSetReader:
    """File-backed GoldSetReader adapter."""

    def __init__(self, *, path: Path) -> None:
        self._path = path

    def get_gold_set(self, name: str) -> IntentClassificationGoldSet:
        raw = yaml.safe_load(self._path.read_text())
        if not isinstance(raw, dict):
            raise ValueError(
                f"gold-set fixture at {self._path} must be a mapping; "
                f"got {type(raw).__name__}"
            )
        if raw.get("name") != name:
            raise KeyError(
                f"gold-set fixture at {self._path} carries name "
                f"{raw.get('name')!r}, not {name!r}"
            )
        entries_raw = raw.get("entries", ())
        if not isinstance(entries_raw, list) or not entries_raw:
            raise ValueError(
                f"gold-set fixture at {self._path} must carry a non-empty "
                "entries list"
            )
        entries = tuple(
            IntentClassificationGoldSetEntry(
                input_phrasing=e["input_phrasing"],
                expected_intent_class=e["expected_intent_class"],
                expected_confidence_minimum=e.get(
                    "expected_confidence_minimum"
                ),
            )
            for e in entries_raw
        )
        # Per S51 Finding 3 disposition: extending INTENT_CLASSES tuple is
        # the cheapest adaptation for the second intent surface; the
        # gold-set's intent_surface field selects which prompt+schema the
        # runner uses. Defaults to manual_entry for backward compatibility
        # with S48b fixtures that pre-date the field.
        intent_surface_raw = raw.get("intent_surface")
        if intent_surface_raw is None:
            return IntentClassificationGoldSet(name=name, entries=entries)
        return IntentClassificationGoldSet(
            name=name, entries=entries, intent_surface=str(intent_surface_raw)
        )


__all__ = ["YamlGoldSetReader"]
