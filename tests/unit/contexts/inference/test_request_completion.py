from __future__ import annotations

from typing import Sequence

from contexts.inference.api import request_completion
from contexts.inference.domain.completion import (
    Completion,
    Message,
    TokenUsage,
)
from shared_kernel import TenantId


class _FakeInferencePort:
    def __init__(self) -> None:
        self.calls: list[
            tuple[Sequence[Message], str | None, TenantId]
        ] = []

    def complete(
        self,
        messages: Sequence[Message],
        model: str | None,
        tenant_id: TenantId,
    ) -> Completion:
        self.calls.append((messages, model, tenant_id))
        return Completion(
            text="hi",
            model=model or "default",
            usage=TokenUsage(input_tokens=4, output_tokens=2),
        )


def test_use_case_passes_arguments_to_port() -> None:
    port = _FakeInferencePort()
    messages = [Message(role="user", content="hello")]

    result = request_completion(
        port=port,
        messages=messages,
        model="qwen2.5:7b",
        tenant_id=TenantId("tenant-a"),
    )

    assert result.text == "hi"
    assert result.usage.total_tokens == 6
    assert port.calls == [(messages, "qwen2.5:7b", TenantId("tenant-a"))]


def test_use_case_passes_none_model_through() -> None:
    port = _FakeInferencePort()

    result = request_completion(
        port=port,
        messages=[Message(role="user", content="x")],
        model=None,
        tenant_id=TenantId("tenant-a"),
    )

    assert result.model == "default"
    assert port.calls[0][1] is None


def test_completion_carries_trace_id_when_set() -> None:
    completion = Completion(
        text="hi",
        model="qwen2.5:7b",
        usage=TokenUsage(input_tokens=4, output_tokens=2),
        trace_id="abc123",
        finish_reason="stop",
    )
    assert completion.trace_id == "abc123"
    assert completion.finish_reason == "stop"
