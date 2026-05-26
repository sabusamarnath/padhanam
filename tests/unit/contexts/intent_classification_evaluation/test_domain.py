"""Domain-layer unit tests for intent-classification evaluation (D137, S48b)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.intent_classification_evaluation.domain.evaluation_result import (
    EvaluationAggregate,
    EvaluationResult,
)
from contexts.intent_classification_evaluation.domain.evaluation_run import (
    EvaluationRun,
    EvaluationRunStatus,
    utcnow,
)
from contexts.intent_classification_evaluation.domain.gold_set import (
    DEFAULT_INTENT_SURFACE,
    INTENT_CLASSES,
    INTENT_SURFACES,
    IntentClassificationGoldSet,
    IntentClassificationGoldSetEntry,
)
from contexts.intent_classification_evaluation.domain.metrics import (
    compute_aggregates,
    compute_is_correct,
)
from shared_kernel.inference import (
    DEFAULT_ACCOUNT,
    LatencyTier,
    ModelConfiguration,
    ModelIdentifier,
    Provider,
)


def _model_identifier(version: str = "gpt-4o-mini") -> ModelIdentifier:
    return ModelIdentifier(
        provider=Provider.OPENAI,
        account=DEFAULT_ACCOUNT,
        version=version,
        configuration=ModelConfiguration(
            latency_tier=LatencyTier.REAL_TIME_REQUIRED,
            temperature=0.0,
            max_tokens=None,
            structured_output_schema=None,
        ),
    )


class TestGoldSetEntry:
    def test_happy_path(self) -> None:
        entry = IntentClassificationGoldSetEntry(
            input_phrasing="Create a case for the Q3 review",
            expected_intent_class="create_case",
        )
        assert entry.expected_confidence_minimum is None

    def test_rejects_empty_input(self) -> None:
        with pytest.raises(ValueError, match="input_phrasing"):
            IntentClassificationGoldSetEntry(
                input_phrasing="",
                expected_intent_class="create_case",
            )

    def test_rejects_unknown_intent_class(self) -> None:
        with pytest.raises(ValueError, match="expected_intent_class"):
            IntentClassificationGoldSetEntry(
                input_phrasing="anything",
                expected_intent_class="not_a_class",
            )

    def test_rejects_confidence_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="confidence_minimum"):
            IntentClassificationGoldSetEntry(
                input_phrasing="anything",
                expected_intent_class="create_case",
                expected_confidence_minimum=1.5,
            )


class TestGoldSet:
    def test_happy_path(self) -> None:
        gs = IntentClassificationGoldSet(
            name="test",
            entries=(
                IntentClassificationGoldSetEntry(
                    input_phrasing="hello",
                    expected_intent_class="create_case",
                ),
            ),
        )
        assert gs.name == "test"
        assert len(gs.entries) == 1

    def test_rejects_empty_entries(self) -> None:
        with pytest.raises(ValueError, match="entries"):
            IntentClassificationGoldSet(name="test", entries=())


class TestEvaluationRunLifecycle:
    def test_mark_completed_transitions_from_running(self) -> None:
        run = EvaluationRun(
            id=uuid4(),
            tenant_id=uuid4(),
            gold_set_name="test",
            model_identifier=_model_identifier(),
            status=EvaluationRunStatus.RUNNING,
            started_at=utcnow(),
            completed_at=None,
            failure_reason=None,
        )
        completed = run.mark_completed(at=utcnow())
        assert completed.status is EvaluationRunStatus.COMPLETED
        assert completed.completed_at is not None
        assert completed.failure_reason is None

    def test_mark_failed_transitions_from_running(self) -> None:
        run = EvaluationRun(
            id=uuid4(),
            tenant_id=uuid4(),
            gold_set_name="test",
            model_identifier=_model_identifier(),
            status=EvaluationRunStatus.RUNNING,
            started_at=utcnow(),
            completed_at=None,
            failure_reason=None,
        )
        failed = run.mark_failed(at=utcnow(), reason="adapter timeout")
        assert failed.status is EvaluationRunStatus.FAILED
        assert failed.failure_reason == "adapter timeout"

    def test_cannot_transition_from_completed(self) -> None:
        completed = EvaluationRun(
            id=uuid4(),
            tenant_id=uuid4(),
            gold_set_name="test",
            model_identifier=_model_identifier(),
            status=EvaluationRunStatus.COMPLETED,
            started_at=utcnow(),
            completed_at=utcnow(),
            failure_reason=None,
        )
        with pytest.raises(ValueError, match="running"):
            completed.mark_completed(at=utcnow())
        with pytest.raises(ValueError, match="running"):
            completed.mark_failed(at=utcnow(), reason="x")

    def test_rejects_naive_timestamps(self) -> None:
        with pytest.raises(ValueError, match="tz-aware"):
            EvaluationRun(
                id=uuid4(),
                tenant_id=uuid4(),
                gold_set_name="test",
                model_identifier=_model_identifier(),
                status=EvaluationRunStatus.RUNNING,
                started_at=datetime(2026, 1, 1),
                completed_at=None,
                failure_reason=None,
            )


class TestComputeIsCorrect:
    def test_correct_classification(self) -> None:
        assert compute_is_correct(
            expected_intent_class="create_case",
            classified_intent_class="create_case",
            confidence=0.9,
            expected_confidence_minimum=None,
            parse_failure=False,
        )

    def test_parse_failure_is_never_correct(self) -> None:
        assert not compute_is_correct(
            expected_intent_class="create_case",
            classified_intent_class="create_case",
            confidence=0.9,
            expected_confidence_minimum=None,
            parse_failure=True,
        )

    def test_mismatched_class_not_correct(self) -> None:
        assert not compute_is_correct(
            expected_intent_class="create_case",
            classified_intent_class="add_data_point",
            confidence=0.9,
            expected_confidence_minimum=None,
            parse_failure=False,
        )

    def test_below_confidence_threshold_not_correct(self) -> None:
        assert not compute_is_correct(
            expected_intent_class="create_case",
            classified_intent_class="create_case",
            confidence=0.5,
            expected_confidence_minimum=0.8,
            parse_failure=False,
        )

    def test_above_confidence_threshold_correct(self) -> None:
        assert compute_is_correct(
            expected_intent_class="create_case",
            classified_intent_class="create_case",
            confidence=0.85,
            expected_confidence_minimum=0.8,
            parse_failure=False,
        )


class TestComputeAggregates:
    def test_per_class_aggregates(self) -> None:
        run_id = uuid4()
        results = tuple(
            EvaluationResult(
                run_id=run_id,
                entry_index=i,
                input_phrasing=f"input {i}",
                expected_intent_class="create_case",
                classified_intent_class=(
                    "create_case" if i < 3 else "add_data_point"
                ),
                confidence=0.8,
                latency_ms=100,
                parse_failure=False,
                is_correct=(i < 3),
            )
            for i in range(4)
        )
        aggs = compute_aggregates(run_id=run_id, results=results)
        assert len(aggs) == len(INTENT_CLASSES)
        by_class = {a.intent_class: a for a in aggs}
        cc = by_class["create_case"]
        assert cc.support == 4
        assert cc.correct_count == 3
        assert cc.accuracy == pytest.approx(0.75)
        assert cc.recall == pytest.approx(0.75)
        adp = by_class["add_data_point"]
        assert adp.support == 0
        # We classified 1 entry as add_data_point but its expected was
        # create_case — so precision for add_data_point is 0.0
        assert adp.precision == pytest.approx(0.0)


# ----------------------------------------------------------------- S51


def test_intent_surface_defaults_to_manual_entry() -> None:
    """Backward compatibility: gold sets without intent_surface default to manual_entry."""
    gs = IntentClassificationGoldSet(
        name="legacy",
        entries=(
            IntentClassificationGoldSetEntry(
                input_phrasing="x",
                expected_intent_class="create_case",
            ),
        ),
    )
    assert gs.intent_surface == DEFAULT_INTENT_SURFACE == "manual_entry"


def test_intent_surface_accepts_audit_conversation() -> None:
    gs = IntentClassificationGoldSet(
        name="audit",
        entries=(
            IntentClassificationGoldSetEntry(
                input_phrasing="show audit for today",
                expected_intent_class="find_by_date_range",
            ),
        ),
        intent_surface="audit_conversation",
    )
    assert gs.intent_surface == "audit_conversation"


def test_intent_surface_rejects_unknown_surface() -> None:
    with pytest.raises(ValueError, match="intent_surface"):
        IntentClassificationGoldSet(
            name="x",
            entries=(
                IntentClassificationGoldSetEntry(
                    input_phrasing="y", expected_intent_class="unclear"
                ),
            ),
            intent_surface="mirror_conversation",  # not yet a registered surface
        )


def test_intent_classes_carries_both_surfaces_after_s51() -> None:
    """The INTENT_CLASSES tuple extension at S51 admits both surfaces' classes."""
    assert "create_case" in INTENT_CLASSES
    assert "find_by_case" in INTENT_CLASSES
    assert "find_by_combination" in INTENT_CLASSES


def test_intent_surfaces_carries_known_surfaces() -> None:
    assert "manual_entry" in INTENT_SURFACES
    assert "audit_conversation" in INTENT_SURFACES


def test_gold_set_entry_audit_intent_class_accepted() -> None:
    """Audit-conversation intent classes are valid entry expected_intent_class values."""
    entry = IntentClassificationGoldSetEntry(
        input_phrasing="show audit for today",
        expected_intent_class="find_by_date_range",
    )
    assert entry.expected_intent_class == "find_by_date_range"
