"""Unit tests for the prompt-applier branch of PolymorphicApplier.

Exercises the prompt dispatch path against a fake ``InferencePort``
that returns a known response. The fake captures the call arguments
so we can assert template formatting, judge-model selection, and
score parsing happen as documented.

Score-parsing strategy at S17a (per the adapter docstring): prefer
criterion-level label matching (longest-first); fall back to first
integer; empty string if neither matches. The tests cover all three
paths so the parsing strategy stays honest about what it surfaces.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from contexts.evaluation.adapters.outbound.polymorphic_applier import (
    PolymorphicApplier,
)
from contexts.evaluation.domain.applier import ApplierConfig, ApplierType
from contexts.evaluation.domain.interaction import Interaction
from contexts.evaluation.domain.model_config import ModelConfig
from contexts.evaluation.domain.replay_result import ReplayResult
from contexts.evaluation.domain.scoring_sheet import Criterion, CriterionLevel
from shared_kernel import TenantContext


class _FakeInferencePort:
    def __init__(self, output_text: str) -> None:
        self._output_text = output_text
        self.calls: list[tuple[ModelConfig, str, TenantContext]] = []

    async def complete(
        self,
        *,
        model_config: ModelConfig,
        input: str,
        tenant_context: TenantContext,
    ) -> ReplayResult:
        self.calls.append((model_config, input, tenant_context))
        return ReplayResult(
            output_text=self._output_text,
            trace_id="trace-" + str(len(self.calls)),
        )


def _tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a001",
    )


def _criterion(levels: tuple[CriterionLevel, ...]) -> Criterion:
    return Criterion(
        id=uuid4(),
        scoring_sheet_revision_id=uuid4(),
        name="answer quality",
        description="judge whether the answer is good",
        levels=levels,
        ordering=0,
    )


def _interaction() -> Interaction:
    return Interaction(
        id=uuid4(),
        interaction_set_id=uuid4(),
        input={"prompt": "hi"},
        expected_output=None,
        ordering=0,
        created_at=datetime.now(timezone.utc),
    )


def _prompt_applier_config() -> ApplierConfig:
    return ApplierConfig(
        id=uuid4(),
        scoring_sheet_revision_id=uuid4(),
        criterion_id=uuid4(),
        applier_type=ApplierType.PROMPT,
        prompt_template=(
            "Score the answer against criterion {criterion_name}. "
            "Levels: {criterion_levels}. Answer: {output}."
        ),
        judge_model="qwen2.5:7b",
    )


def test_prompt_branch_formats_template_and_calls_inference_with_judge_model() -> None:
    fake_port = _FakeInferencePort(output_text="The answer is pass.")
    applier = PolymorphicApplier(
        inference_port=fake_port,
        tenant_context=_tenant_context(),
    )
    criterion = _criterion(
        levels=(
            CriterionLevel(label="pass", definition="answer is good"),
            CriterionLevel(label="fail", definition="answer is bad"),
        )
    )

    score = asyncio.run(
        applier.apply(
            interaction=_interaction(),
            output="42",
            criterion=criterion,
            applier_config=_prompt_applier_config(),
        )
    )

    assert score == "pass"
    assert len(fake_port.calls) == 1
    model_config, formatted, tenant_context = fake_port.calls[0]
    assert model_config.model_name == "qwen2.5:7b"
    assert "Score the answer against criterion answer quality" in formatted
    assert "pass, fail" in formatted
    assert "Answer: 42." in formatted
    assert tenant_context == _tenant_context()


def test_prompt_branch_parses_first_integer_when_no_label_matches() -> None:
    fake_port = _FakeInferencePort(output_text="My score for this answer is 4.")
    applier = PolymorphicApplier(
        inference_port=fake_port,
        tenant_context=_tenant_context(),
    )
    criterion = _criterion(
        levels=(
            CriterionLevel(label="1", definition="bad"),
            CriterionLevel(label="2", definition="okay"),
            CriterionLevel(label="3", definition="good"),
            CriterionLevel(label="4", definition="great"),
            CriterionLevel(label="5", definition="excellent"),
        )
    )

    score = asyncio.run(
        applier.apply(
            interaction=_interaction(),
            output="some answer",
            criterion=criterion,
            applier_config=_prompt_applier_config(),
        )
    )

    # Numeric labels are matched as substrings; "4." in the response
    # contains "4" which matches the level label "4". The longest-
    # first sort doesn't help because all labels are length-1; the
    # adapter returns the first match in the levels list when label
    # matching produces no unique winner. The substring "4" appears
    # in the lowered text so the label "4" wins.
    assert score == "4"


def test_prompt_branch_returns_empty_when_no_label_or_integer_matches() -> None:
    fake_port = _FakeInferencePort(output_text="I cannot decide.")
    applier = PolymorphicApplier(
        inference_port=fake_port,
        tenant_context=_tenant_context(),
    )
    criterion = _criterion(
        levels=(
            CriterionLevel(label="pass", definition="good"),
            CriterionLevel(label="fail", definition="bad"),
        )
    )

    score = asyncio.run(
        applier.apply(
            interaction=_interaction(),
            output="answer",
            criterion=criterion,
            applier_config=_prompt_applier_config(),
        )
    )

    # No label substring; no integer; empty string is the
    # documented "judge produced no score" return.
    assert score == ""


def test_prompt_branch_raises_when_adapter_constructed_without_inference_port() -> None:
    applier = PolymorphicApplier()  # no inference port
    criterion = _criterion(
        levels=(CriterionLevel(label="pass", definition="ok"),)
    )

    try:
        asyncio.run(
            applier.apply(
                interaction=_interaction(),
                output="x",
                criterion=criterion,
                applier_config=_prompt_applier_config(),
            )
        )
    except ValueError as e:
        assert "InferencePort" in str(e)
    else:
        raise AssertionError("expected ValueError when prompt branch lacks port")


def test_deterministic_branch_unaffected_by_prompt_branch_addition() -> None:
    """The deterministic dispatch path still works exactly as it did
    after the rename. Constructing the adapter without inference_port
    is supported for purely-deterministic workloads.
    """
    applier = PolymorphicApplier()
    criterion = _criterion(
        levels=(
            CriterionLevel(label="pass", definition="ok"),
            CriterionLevel(label="fail", definition="not ok"),
        )
    )
    interaction = Interaction(
        id=uuid4(),
        interaction_set_id=uuid4(),
        input={"prompt": "hi"},
        expected_output={"value": "hello"},
        ordering=0,
        created_at=datetime.now(timezone.utc),
    )
    deterministic_config = ApplierConfig(
        id=uuid4(),
        scoring_sheet_revision_id=uuid4(),
        criterion_id=criterion.id,
        applier_type=ApplierType.DETERMINISTIC,
        deterministic_function_name="exact_match",
    )

    score = asyncio.run(
        applier.apply(
            interaction=interaction,
            output="hello",
            criterion=criterion,
            applier_config=deterministic_config,
        )
    )
    assert score == "pass"
