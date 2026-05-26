"""Classification accuracy metrics for intent-classification evaluation (D137, S48b).

Pure-function primitives operating on tuples of ``EvaluationResult``.
Used by the application layer to compute ``EvaluationAggregate``
records after a run completes.

Per the same vendor-flexibility pattern at D111 (MetricCalculator
pluggable abstraction), these primitives are pure functions today;
future evolution into a MetricCalculator port-and-adapter shape
activates if multiple methodologies for computing classification
metrics emerge.
"""

from __future__ import annotations

from uuid import UUID

from contexts.intent_classification_evaluation.domain.evaluation_result import (
    EvaluationAggregate,
    EvaluationResult,
)
from contexts.intent_classification_evaluation.domain.gold_set import (
    INTENT_CLASSES,
)


def compute_is_correct(
    *,
    expected_intent_class: str,
    classified_intent_class: str,
    confidence: float | None,
    expected_confidence_minimum: float | None,
    parse_failure: bool,
) -> bool:
    """Compute the is_correct flag for one classification result.

    Parse failure is never correct. Classification-match plus
    confidence-above-threshold (when threshold is set) is correct.
    Confidence-below-threshold even on a matching classification is
    not correct — the entry's optional minimum encodes the
    "model must classify AND be sufficiently confident" expectation.
    """
    if parse_failure:
        return False
    if classified_intent_class != expected_intent_class:
        return False
    if expected_confidence_minimum is None:
        return True
    if confidence is None:
        return False
    return confidence >= expected_confidence_minimum


def compute_aggregates(
    *, run_id: UUID, results: tuple[EvaluationResult, ...]
) -> tuple[EvaluationAggregate, ...]:
    """Compute per-class EvaluationAggregate records from per-entry results.

    Iterates the four canonical intent classes; for each:
    - ``support`` is the count of entries whose expected_intent_class
      matches.
    - ``correct_count`` is the count of entries with matching expected
      class and ``is_correct=True``.
    - ``parse_failure_count`` is the count of entries with matching
      expected class and ``parse_failure=True``.
    - ``accuracy`` = correct_count / support (or 0 when support is 0).
    - ``recall`` = same as accuracy at this granularity.
    - ``precision`` = of all entries classified-as-this-class, what
      fraction had this expected class.
    """
    aggregates: list[EvaluationAggregate] = []
    for intent_class in INTENT_CLASSES:
        # Entries whose expected class is intent_class
        expected = tuple(
            r for r in results if r.expected_intent_class == intent_class
        )
        support = len(expected)
        correct = sum(1 for r in expected if r.is_correct)
        parse_failures = sum(1 for r in expected if r.parse_failure)
        accuracy = correct / support if support > 0 else 0.0

        # Entries whose classified class is intent_class
        predicted = tuple(
            r
            for r in results
            if not r.parse_failure and r.classified_intent_class == intent_class
        )
        predicted_count = len(predicted)
        true_positives = sum(
            1 for r in predicted if r.expected_intent_class == intent_class
        )
        precision = (
            true_positives / predicted_count if predicted_count > 0 else 0.0
        )

        aggregates.append(
            EvaluationAggregate(
                run_id=run_id,
                intent_class=intent_class,
                support=support,
                correct_count=correct,
                parse_failure_count=parse_failures,
                accuracy=accuracy,
                recall=accuracy,
                precision=precision,
            )
        )
    return tuple(aggregates)


__all__ = ["compute_aggregates", "compute_is_correct"]
