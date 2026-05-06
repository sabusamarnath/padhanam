"""Unit test for InferenceAdapter.

Exercises the adapter against a fake inference port (the inference
context's ``InferencePort`` shape) and asserts:

  - the adapter constructs a single user-role ``Message`` from the
    input text;
  - the adapter passes ``model_config.model_name`` through as the
    ``model`` parameter to ``request_completion``;
  - the adapter returns a ``ReplayResult`` with ``output_text``
    and ``trace_id`` lifted from the inference ``Completion``;
  - when ``Completion.trace_id`` is ``None``, ``ReplayResult.trace_id``
    is the empty string (downstream cost queries skip empties).
"""

from __future__ import annotations

import asyncio
from typing import Sequence

from contexts.evaluation.adapters.outbound.inference_adapter import (
    InferenceAdapter,
)
from contexts.evaluation.domain.model_config import ModelConfig
from contexts.inference.domain.completion import (
    Completion,
    Message,
    TokenUsage,
)
from shared_kernel import TenantContext


class _FakeInferencePort:
    def __init__(self, completion: Completion) -> None:
        self._completion = completion
        self.calls: list[
            tuple[Sequence[Message], str | None, TenantContext]
        ] = []

    def complete(
        self,
        messages: Sequence[Message],
        model: str | None,
        tenant_context: TenantContext,
    ) -> Completion:
        self.calls.append((list(messages), model, tenant_context))
        return self._completion


def _tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a001",
    )


def test_adapter_threads_model_and_input_into_inference_port() -> None:
    completion = Completion(
        text="hello",
        model="qwen2.5:7b",
        usage=TokenUsage(input_tokens=4, output_tokens=1),
        trace_id="abcd1234" * 4,
    )
    fake_port = _FakeInferencePort(completion)
    adapter = InferenceAdapter(inference_port=fake_port)

    result = asyncio.run(
        adapter.complete(
            model_config=ModelConfig(model_name="qwen2.5:7b"),
            input="say hello",
            tenant_context=_tenant_context(),
        )
    )

    assert result.output_text == "hello"
    assert result.trace_id == "abcd1234" * 4
    assert len(fake_port.calls) == 1
    messages, model, tc = fake_port.calls[0]
    assert model == "qwen2.5:7b"
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "say hello"
    assert tc == _tenant_context()


def test_adapter_returns_empty_trace_id_when_completion_has_none() -> None:
    completion = Completion(
        text="output",
        model="qwen2.5:7b",
        usage=TokenUsage(input_tokens=1, output_tokens=1),
        trace_id=None,
    )
    fake_port = _FakeInferencePort(completion)
    adapter = InferenceAdapter(inference_port=fake_port)

    result = asyncio.run(
        adapter.complete(
            model_config=ModelConfig(model_name="qwen2.5:7b"),
            input="anything",
            tenant_context=_tenant_context(),
        )
    )

    assert result.output_text == "output"
    assert result.trace_id == ""
