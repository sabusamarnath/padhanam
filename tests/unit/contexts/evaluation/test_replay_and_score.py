"""Unit tests for the replay_and_score orchestrator.

Exercises the orchestrator with fake ports and a stub
``apply_scoring_sheet`` callable. Asserts:

  - the orchestrator iterates the interactions returned by the
    repository, calling inference once per interaction;
  - each apply_scoring_sheet invocation receives the trace_id from
    the matching ReplayResult;
  - the orchestrator threads model_config and tenant_context through
    every inference call;
  - empty interaction sets produce empty rubric_application lists.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from contexts.evaluation.application.replay_and_score import replay_and_score
from contexts.evaluation.domain.applier import ApplierConfig, ApplierType
from contexts.evaluation.domain.interaction import Interaction
from contexts.evaluation.domain.model_config import ModelConfig
from contexts.evaluation.domain.replay_result import ReplayResult
from contexts.evaluation.domain.rubric_application import RubricApplication
from shared_kernel import TenantContext


class _FakeInferencePort:
    def __init__(self, results_by_input: dict[str, ReplayResult]) -> None:
        self._results = results_by_input
        self.calls: list[tuple[ModelConfig, str, TenantContext]] = []

    async def complete(
        self,
        *,
        model_config: ModelConfig,
        input: str,
        tenant_context: TenantContext,
    ) -> ReplayResult:
        self.calls.append((model_config, input, tenant_context))
        return self._results[input]


class _FakeInteractionRepository:
    def __init__(self, interactions: list[Interaction]) -> None:
        self._interactions = interactions
        self.calls: list[UUID] = []

    async def list_by_set_id(
        self, interaction_set_id: UUID
    ) -> list[Interaction]:
        self.calls.append(interaction_set_id)
        return self._interactions


def _tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a001",
    )


def _interaction(prompt: str, ordering: int) -> Interaction:
    return Interaction(
        id=uuid4(),
        interaction_set_id=uuid4(),
        input={"prompt": prompt},
        expected_output={"value": prompt + "!"},
        ordering=ordering,
        created_at=datetime.now(timezone.utc),
    )


def test_orchestrator_calls_inference_once_per_interaction_and_threads_trace_id() -> None:
    revision_id = uuid4()
    interaction_set_id = uuid4()
    interaction_a = _interaction("hello", 0)
    interaction_b = _interaction("goodbye", 1)
    interactions = [interaction_a, interaction_b]
    inference_port = _FakeInferencePort(
        {
            "hello": ReplayResult(
                output_text="hi there", trace_id="trace-a"
            ),
            "goodbye": ReplayResult(
                output_text="see ya", trace_id="trace-b"
            ),
        }
    )
    interaction_repo = _FakeInteractionRepository(interactions)

    captured_apply_calls: list[dict[str, Any]] = []

    async def _stub_apply_scoring_sheet(**kwargs: Any) -> list[RubricApplication]:
        captured_apply_calls.append(kwargs)
        # Return a single dummy RubricApplication per call so the
        # orchestrator's flat-extend semantics are exercised.
        interaction = kwargs["interaction"]
        return [
            RubricApplication(
                id=uuid4(),
                scoring_sheet_revision_id=revision_id,
                criterion_id=uuid4(),
                interaction_id=interaction.id,
                applier_id=uuid4(),
                automated_score="ok",
                human_score=None,
                reviewed_by_user_id=None,
                confirmed_at=None,
                created_at=datetime.now(timezone.utc),
                trace_id=kwargs["trace_id"],
            )
        ]

    # Sentinel ports for the repos and applier — the stub
    # apply_scoring_sheet ignores them, but the orchestrator passes
    # them through so we assert the wiring shape.
    sheet_repo = object()
    rubric_repo = object()
    applier = object()

    results = asyncio.run(
        replay_and_score(
            tenant_context=_tenant_context(),
            scoring_sheet_revision_id=revision_id,
            interaction_set_id=interaction_set_id,
            model_config=ModelConfig(model_name="qwen2.5:7b"),
            inference_port=inference_port,
            interaction_repository=interaction_repo,
            scoring_sheet_repository=sheet_repo,  # type: ignore[arg-type]
            rubric_application_repository=rubric_repo,  # type: ignore[arg-type]
            applier=applier,  # type: ignore[arg-type]
            apply_scoring_sheet=_stub_apply_scoring_sheet,
        )
    )

    # Repository called once with the set id.
    assert interaction_repo.calls == [interaction_set_id]
    # Inference called once per interaction, in order, with the
    # interaction's prompt and the same model config and tenant context.
    assert len(inference_port.calls) == 2
    mc_a, input_a, tc_a = inference_port.calls[0]
    mc_b, input_b, tc_b = inference_port.calls[1]
    assert mc_a.model_name == "qwen2.5:7b"
    assert mc_b.model_name == "qwen2.5:7b"
    assert input_a == "hello"
    assert input_b == "goodbye"
    assert tc_a == _tenant_context()
    assert tc_b == _tenant_context()
    # apply_scoring_sheet called once per interaction, with the
    # trace_id from the matching ReplayResult.
    assert len(captured_apply_calls) == 2
    assert captured_apply_calls[0]["trace_id"] == "trace-a"
    assert captured_apply_calls[0]["interaction"].id == interaction_a.id
    assert captured_apply_calls[0]["output"] == "hi there"
    assert captured_apply_calls[1]["trace_id"] == "trace-b"
    assert captured_apply_calls[1]["interaction"].id == interaction_b.id
    assert captured_apply_calls[1]["output"] == "see ya"
    # The orchestrator's return is the flat extension of every
    # apply_scoring_sheet result; here that is two records (one per
    # interaction).
    assert len(results) == 2
    assert {r.trace_id for r in results} == {"trace-a", "trace-b"}


def test_orchestrator_returns_empty_when_set_has_no_interactions() -> None:
    interaction_repo = _FakeInteractionRepository(interactions=[])
    inference_port = _FakeInferencePort({})

    async def _stub_apply_scoring_sheet(**kwargs: Any) -> list[RubricApplication]:
        raise AssertionError(
            "apply_scoring_sheet should not be invoked for an empty set"
        )

    results = asyncio.run(
        replay_and_score(
            tenant_context=_tenant_context(),
            scoring_sheet_revision_id=uuid4(),
            interaction_set_id=uuid4(),
            model_config=ModelConfig(model_name="qwen2.5:7b"),
            inference_port=inference_port,
            interaction_repository=interaction_repo,
            scoring_sheet_repository=object(),  # type: ignore[arg-type]
            rubric_application_repository=object(),  # type: ignore[arg-type]
            applier=object(),  # type: ignore[arg-type]
            apply_scoring_sheet=_stub_apply_scoring_sheet,
        )
    )

    assert results == []
    assert inference_port.calls == []


def test_orchestrator_threads_empty_trace_id_as_none() -> None:
    """When the inference adapter returns an empty trace_id (e.g. no
    active OTel span context at test time), the orchestrator passes
    ``None`` rather than the empty string into apply_scoring_sheet so
    the rubric_applications row stores NULL — distinguishable in
    cost-query joins from a trace that exists but has no cost data.
    """
    revision_id = uuid4()
    interaction = _interaction("input", 0)
    inference_port = _FakeInferencePort(
        {"input": ReplayResult(output_text="output", trace_id="")}
    )

    captured: list[str | None] = []

    async def _stub_apply_scoring_sheet(**kwargs: Any) -> list[RubricApplication]:
        captured.append(kwargs["trace_id"])
        return []

    asyncio.run(
        replay_and_score(
            tenant_context=_tenant_context(),
            scoring_sheet_revision_id=revision_id,
            interaction_set_id=uuid4(),
            model_config=ModelConfig(model_name="qwen2.5:7b"),
            inference_port=inference_port,
            interaction_repository=_FakeInteractionRepository([interaction]),
            scoring_sheet_repository=object(),  # type: ignore[arg-type]
            rubric_application_repository=object(),  # type: ignore[arg-type]
            applier=object(),  # type: ignore[arg-type]
            apply_scoring_sheet=_stub_apply_scoring_sheet,
        )
    )

    assert captured == [None]
