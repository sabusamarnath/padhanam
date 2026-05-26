"""EvaluationResult and EvaluationAggregate value objects (D137, S48b).

A run produces one EvaluationResult per gold-set entry plus one
EvaluationAggregate per intent class. The aggregates are computed
by ``contexts.intent_classification_evaluation.domain.metrics`` from
the per-entry results.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class EvaluationResult:
    """One model's classification of one gold-set entry.

    ``classified_intent_class`` is the model's classification result
    (one of the four intent classes, or empty string when parse_failure
    is true). ``confidence`` is the model's self-reported confidence
    (0.0-1.0). ``latency_ms`` is the per-call latency in milliseconds.
    ``parse_failure`` is true when the model produced output that
    did not parse against the schema (per D134's
    StructuredOutputParseFailure surface). ``is_correct`` is precomputed
    from comparing classified vs expected, taking
    ``expected_confidence_minimum`` into account if set on the entry.
    """

    run_id: UUID
    entry_index: int
    input_phrasing: str
    expected_intent_class: str
    classified_intent_class: str
    confidence: float | None
    latency_ms: int
    parse_failure: bool
    is_correct: bool

    def __post_init__(self) -> None:
        if self.entry_index < 0:
            raise ValueError("EvaluationResult.entry_index must be >= 0")
        if self.latency_ms < 0:
            raise ValueError("EvaluationResult.latency_ms must be >= 0")
        if self.confidence is not None and not (
            0.0 <= self.confidence <= 1.0
        ):
            raise ValueError(
                f"EvaluationResult.confidence must be in [0.0, 1.0]; "
                f"got {self.confidence!r}"
            )


@dataclass(frozen=True)
class EvaluationAggregate:
    """Per-intent-class metrics for one run.

    The four standard classification metrics:
    - ``accuracy`` over entries with this expected class — what
      fraction were classified correctly.
    - ``recall`` is the same number as accuracy when the per-class
      view is "of all entries that *should* be class X, what
      fraction did we classify as X".
    - ``precision`` is the dual — "of all entries we classified as
      class X, what fraction *should* have been X".
    - ``support`` is the count of gold-set entries with this expected
      class (the denominator for recall).
    """

    run_id: UUID
    intent_class: str
    support: int
    correct_count: int
    parse_failure_count: int
    accuracy: float
    recall: float
    precision: float

    def __post_init__(self) -> None:
        if self.support < 0:
            raise ValueError("EvaluationAggregate.support must be >= 0")
        if self.correct_count < 0:
            raise ValueError(
                "EvaluationAggregate.correct_count must be >= 0"
            )
        if self.correct_count > self.support:
            raise ValueError(
                "EvaluationAggregate.correct_count cannot exceed support"
            )
        for name, value in (
            ("accuracy", self.accuracy),
            ("recall", self.recall),
            ("precision", self.precision),
        ):
            if not (0.0 <= value <= 1.0):
                raise ValueError(
                    f"EvaluationAggregate.{name} must be in [0.0, 1.0]; "
                    f"got {value!r}"
                )


__all__ = [
    "EvaluationAggregate",
    "EvaluationResult",
]
