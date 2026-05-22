"""Unit tests for the structured-output discipline (D130, S45)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from shared_kernel.structured_output import (
    StructuredOutputPort,
    StructuredOutputRequest,
    StructuredOutputResponse,
)

_SCHEMA = {
    "type": "object",
    "properties": {"intent": {"type": "string"}},
    "required": ["intent"],
}


def test_request_constructs() -> None:
    request = StructuredOutputRequest(
        prompt="classify the intent of this message",
        schema=_SCHEMA,
        temperature=0.0,
        model_hint="qwen2.5:7b",
    )
    assert request.prompt.startswith("classify")
    assert request.schema == _SCHEMA
    assert request.temperature == 0.0
    assert request.model_hint == "qwen2.5:7b"


def test_request_optional_fields_default_to_none() -> None:
    request = StructuredOutputRequest(prompt="p", schema=_SCHEMA)
    assert request.temperature is None
    assert request.model_hint is None


@pytest.mark.parametrize("bad_prompt", ["", "   "])
def test_request_rejects_empty_prompt(bad_prompt: str) -> None:
    with pytest.raises(ValueError, match="prompt must be non-empty"):
        StructuredOutputRequest(prompt=bad_prompt, schema=_SCHEMA)


def test_request_rejects_empty_schema() -> None:
    with pytest.raises(ValueError, match="schema must be non-empty"):
        StructuredOutputRequest(prompt="p", schema={})


def test_request_is_frozen() -> None:
    request = StructuredOutputRequest(prompt="p", schema=_SCHEMA)
    with pytest.raises(FrozenInstanceError):
        request.prompt = "other"  # type: ignore[misc]


def test_response_carries_value_confidence_and_metadata() -> None:
    response: StructuredOutputResponse[dict[str, object]] = (
        StructuredOutputResponse(
            value={"intent": "reschedule"},
            confidence=0.82,
            provider_metadata={"model": "qwen2.5:7b", "finish": "stop"},
        )
    )
    assert response.value == {"intent": "reschedule"}
    assert response.confidence == 0.82
    assert response.provider_metadata["model"] == "qwen2.5:7b"


def test_response_confidence_may_be_none() -> None:
    response = StructuredOutputResponse(
        value={"intent": "x"}, confidence=None, provider_metadata={}
    )
    assert response.confidence is None


class _ConformingPort:
    async def generate_structured(
        self, request: StructuredOutputRequest
    ) -> StructuredOutputResponse[dict[str, object]]:
        return StructuredOutputResponse(
            value={}, confidence=None, provider_metadata={}
        )


class _NonConformingPort:
    async def something_else(self) -> None: ...


def test_structured_output_port_is_runtime_checkable() -> None:
    assert isinstance(_ConformingPort(), StructuredOutputPort)


def test_non_conforming_class_fails_isinstance() -> None:
    assert not isinstance(_NonConformingPort(), StructuredOutputPort)
