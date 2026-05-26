"""Intent-classification gold-set domain shape (D137, S48b).

Option B simplification: gold-set is loaded from a YAML fixture at
``tests/fixtures/intent_classification/gold_set.yaml`` rather than
persisted with the P11 retrieval-evaluation gold-set's revision-
with-hash-chain lifecycle (D109). The fixture is the canonical
source until the multi-tenant gold-set authoring trigger activates
the revision-lifecycle implementation per D137 alternative (c).

``IntentClassificationGoldSet`` carries the in-memory shape; the
fixture-loader at ``contexts.intent_classification_evaluation.
adapters.outbound.fixture`` constructs an instance from YAML.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass


# The four intent classes the substrate evaluates. Mirrors the
# IntentType StrEnum at contexts/messaging/domain/intent.py; a unit
# test asserts the alignment so the duplication does not drift.
INTENT_CLASSES: tuple[str, ...] = (
    "create_case",
    "add_data_point",
    "revise_data_point",
    "unclear",
)


@dataclass(frozen=True)
class IntentClassificationGoldSetEntry:
    """A single (input, expected) pair in the gold set.

    ``input_phrasing`` is the operator-shaped natural-language input
    the model classifies. ``expected_intent_class`` is the canonical
    correct classification (one of ``INTENT_CLASSES``).
    ``expected_confidence_minimum`` is optional; when set, a result
    is considered correct only if classification matches AND
    confidence is at or above this threshold.
    """

    input_phrasing: str
    expected_intent_class: str
    expected_confidence_minimum: float | None = None

    def __post_init__(self) -> None:
        if not self.input_phrasing or not self.input_phrasing.strip():
            raise ValueError(
                "IntentClassificationGoldSetEntry.input_phrasing must be non-empty"
            )
        if self.expected_intent_class not in INTENT_CLASSES:
            raise ValueError(
                "IntentClassificationGoldSetEntry.expected_intent_class must be "
                f"one of {INTENT_CLASSES}; got {self.expected_intent_class!r}"
            )
        if self.expected_confidence_minimum is not None and not (
            0.0 <= self.expected_confidence_minimum <= 1.0
        ):
            raise ValueError(
                "IntentClassificationGoldSetEntry.expected_confidence_minimum "
                f"must be in [0.0, 1.0]; got {self.expected_confidence_minimum!r}"
            )


@dataclass(frozen=True)
class IntentClassificationGoldSet:
    """The in-memory shape of a gold set.

    ``name`` is the gold-set's identifier (e.g. ``phase_2_a_default``);
    references in ``EvaluationRun.gold_set_name`` carry this value.
    ``entries`` is the ordered tuple of entries the runner iterates.
    """

    name: str
    entries: tuple[IntentClassificationGoldSetEntry, ...]

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("IntentClassificationGoldSet.name must be non-empty")
        if not self.entries:
            raise ValueError(
                "IntentClassificationGoldSet.entries must be non-empty"
            )


__all__ = [
    "INTENT_CLASSES",
    "IntentClassificationGoldSet",
    "IntentClassificationGoldSetEntry",
]
