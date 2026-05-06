"""Unit test for the apply_scoring_sheet use case.

Exercises the use case against in-memory fakes for ``ApplierPort`` and
``RubricApplicationRepositoryPort``. Asserts the use case calls the
applier port once per criterion and persists each result, with the
RubricApplication fields wired correctly (D53 Reading-C posture: the
human-review fields stay null at S16; only ``automated_score`` is
populated by this path).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.evaluation.application.apply_scoring_sheet import (
    apply_scoring_sheet,
)
from contexts.evaluation.domain.applier import ApplierConfig, ApplierType
from contexts.evaluation.domain.interaction import Interaction
from contexts.evaluation.domain.rubric_application import RubricApplication
from contexts.evaluation.domain.scoring_sheet import Criterion, CriterionLevel
from shared_kernel import TenantContext


# ---------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------


class _FakeScoringSheetRepository:
    def __init__(
        self, pairs: list[tuple[Criterion, ApplierConfig]]
    ) -> None:
        self._pairs = pairs
        self.calls: list[UUID] = []

    async def get_criteria_with_appliers(
        self, scoring_sheet_revision_id: UUID
    ) -> list[tuple[Criterion, ApplierConfig]]:
        self.calls.append(scoring_sheet_revision_id)
        return self._pairs


class _FakeRubricApplicationRepository:
    def __init__(self) -> None:
        self.saved: list[RubricApplication] = []

    async def save(self, rubric_application: RubricApplication) -> None:
        self.saved.append(rubric_application)


class _FakeApplier:
    def __init__(self, score_for: dict[str, str]) -> None:
        """``score_for`` maps criterion name → score string."""
        self._score_for = score_for
        self.calls: list[tuple[str, str]] = []

    async def apply(
        self,
        *,
        interaction: Interaction,
        output: str,
        criterion: Criterion,
        applier_config: ApplierConfig,
    ) -> str | None:
        self.calls.append((criterion.name, output))
        return self._score_for.get(criterion.name)


# ---------------------------------------------------------------------
# Fixtures (constructed inline for unit test simplicity)
# ---------------------------------------------------------------------


def _tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a001",
    )


def _criterion(name: str, ordering: int, revision_id: UUID) -> Criterion:
    return Criterion(
        id=uuid4(),
        scoring_sheet_revision_id=revision_id,
        name=name,
        description=f"{name} criterion",
        levels=(
            CriterionLevel(
                label="pass", definition="exact match", is_success=True
            ),
            CriterionLevel(
                label="fail", definition="not exact match", is_success=False
            ),
        ),
        ordering=ordering,
    )


def _applier_config(
    revision_id: UUID, criterion_id: UUID
) -> ApplierConfig:
    return ApplierConfig(
        id=uuid4(),
        scoring_sheet_revision_id=revision_id,
        criterion_id=criterion_id,
        applier_type=ApplierType.DETERMINISTIC,
        deterministic_function_name="exact_match",
    )


def _interaction() -> Interaction:
    return Interaction(
        id=uuid4(),
        interaction_set_id=uuid4(),
        input={"prompt": "say hello"},
        expected_output={"value": "hello"},
        ordering=0,
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------


def test_use_case_calls_applier_once_per_criterion_and_persists_each() -> None:
    revision_id = uuid4()
    crit_a = _criterion("a", 0, revision_id)
    crit_b = _criterion("b", 1, revision_id)
    pairs = [
        (crit_a, _applier_config(revision_id, crit_a.id)),
        (crit_b, _applier_config(revision_id, crit_b.id)),
    ]
    sheet_repo = _FakeScoringSheetRepository(pairs)
    rubric_repo = _FakeRubricApplicationRepository()
    applier = _FakeApplier({"a": "pass", "b": "fail"})
    interaction = _interaction()

    results = asyncio.run(
        apply_scoring_sheet(
            tenant_context=_tenant_context(),
            scoring_sheet_revision_id=revision_id,
            interaction=interaction,
            output="hello",
            scoring_sheet_repository=sheet_repo,
            rubric_application_repository=rubric_repo,
            applier=applier,
        )
    )

    assert sheet_repo.calls == [revision_id]
    assert applier.calls == [("a", "hello"), ("b", "hello")]
    assert len(rubric_repo.saved) == 2
    assert len(results) == 2

    saved_a, saved_b = rubric_repo.saved
    assert saved_a.criterion_id == crit_a.id
    assert saved_a.scoring_sheet_revision_id == revision_id
    assert saved_a.interaction_id == interaction.id
    assert saved_a.automated_score == "pass"
    # D53 Reading-C: human-review fields stay null at S16.
    assert saved_a.human_score is None
    assert saved_a.reviewed_by_user_id is None
    assert saved_a.confirmed_at is None

    assert saved_b.automated_score == "fail"
    assert saved_b.criterion_id == crit_b.id


def test_use_case_persists_trace_id_when_passed() -> None:
    """S17a addition: optional trace_id parameter threads through into
    the persisted RubricApplication record. Backward-compatible: the
    default-None path is exercised by the original tests above.
    """
    revision_id = uuid4()
    crit = _criterion("a", 0, revision_id)
    pairs = [(crit, _applier_config(revision_id, crit.id))]
    sheet_repo = _FakeScoringSheetRepository(pairs)
    rubric_repo = _FakeRubricApplicationRepository()
    applier = _FakeApplier({"a": "pass"})
    interaction = _interaction()

    results = asyncio.run(
        apply_scoring_sheet(
            tenant_context=_tenant_context(),
            scoring_sheet_revision_id=revision_id,
            interaction=interaction,
            output="hello",
            scoring_sheet_repository=sheet_repo,
            rubric_application_repository=rubric_repo,
            applier=applier,
            trace_id="abcd1234" * 4,
        )
    )

    assert len(results) == 1
    assert results[0].trace_id == "abcd1234" * 4
    assert rubric_repo.saved[0].trace_id == "abcd1234" * 4


def test_use_case_returns_empty_when_revision_has_no_criteria() -> None:
    revision_id = uuid4()
    sheet_repo = _FakeScoringSheetRepository(pairs=[])
    rubric_repo = _FakeRubricApplicationRepository()
    applier = _FakeApplier({})

    results = asyncio.run(
        apply_scoring_sheet(
            tenant_context=_tenant_context(),
            scoring_sheet_revision_id=revision_id,
            interaction=_interaction(),
            output="anything",
            scoring_sheet_repository=sheet_repo,
            rubric_application_repository=rubric_repo,
            applier=applier,
        )
    )

    assert results == []
    assert applier.calls == []
    assert rubric_repo.saved == []
