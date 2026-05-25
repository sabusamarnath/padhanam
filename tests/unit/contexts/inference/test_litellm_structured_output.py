"""Unit tests for the LiteLLM adapter's StructuredOutputPort surface (D130, S45).

The structured-output extension is additive — these tests stub
``litellm.acompletion`` at the module-import boundary and assert the
JSON-Schema response_format mapping, the JSON-object parsing, the
confidence-lift rule, and the exception translation.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from litellm.exceptions import BadRequestError, Timeout

from contexts.inference.adapters.outbound.litellm import LiteLLMAdapter
from contexts.inference.domain.errors import (
    InferenceConfigurationError,
    InferenceError,
    InferenceTimeout,
)
from padhanam.config import InferenceSettings
from shared_kernel.structured_output import (
    StructuredOutputParseFailure,
    StructuredOutputPort,
    StructuredOutputRequest,
)

_ACOMPLETION = (
    "contexts.inference.adapters.outbound.litellm.adapter.litellm.acompletion"
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["intent"],
}


def _settings() -> InferenceSettings:
    return InferenceSettings(litellm_master_key="sk-test-key")


def _response(content: str, *, model: str = "qwen2.5:7b") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=8),
        model=model,
    )


def _request(**kw: object) -> StructuredOutputRequest:
    return StructuredOutputRequest(
        prompt=kw.get("prompt", "classify the intent"),  # type: ignore[arg-type]
        schema=kw.get("schema", _SCHEMA),  # type: ignore[arg-type]
        temperature=kw.get("temperature"),  # type: ignore[arg-type]
        model_hint=kw.get("model_hint"),  # type: ignore[arg-type]
    )


def _generate(adapter: LiteLLMAdapter, request: StructuredOutputRequest):
    return asyncio.run(adapter.generate_structured(request))


def test_generate_structured_parses_json_object() -> None:
    adapter = LiteLLMAdapter(settings=_settings())

    async def fake(**kwargs: object) -> SimpleNamespace:
        return _response('{"intent": "reschedule"}')

    with patch(_ACOMPLETION, new=fake):
        result = _generate(adapter, _request())

    assert result.value == {"intent": "reschedule"}
    assert result.provider_metadata["model"] == "qwen2.5:7b"
    assert result.provider_metadata["input_tokens"] == 20
    assert result.provider_metadata["output_tokens"] == 8
    assert result.provider_metadata["finish_reason"] == "stop"


def test_generate_structured_lifts_confidence_field() -> None:
    adapter = LiteLLMAdapter(settings=_settings())

    async def fake(**kwargs: object) -> SimpleNamespace:
        return _response('{"intent": "reschedule", "confidence": 0.87}')

    with patch(_ACOMPLETION, new=fake):
        result = _generate(adapter, _request())

    assert result.confidence == 0.87


def test_generate_structured_confidence_none_without_field() -> None:
    adapter = LiteLLMAdapter(settings=_settings())

    async def fake(**kwargs: object) -> SimpleNamespace:
        return _response('{"intent": "reschedule"}')

    with patch(_ACOMPLETION, new=fake):
        result = _generate(adapter, _request())

    assert result.confidence is None


def test_generate_structured_maps_schema_to_response_format() -> None:
    adapter = LiteLLMAdapter(settings=_settings())
    captured: dict[str, object] = {}

    async def fake(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _response('{"intent": "x"}')

    with patch(_ACOMPLETION, new=fake):
        _generate(adapter, _request(temperature=0.0))

    response_format = captured["response_format"]
    assert response_format["type"] == "json_schema"  # type: ignore[index]
    assert (
        response_format["json_schema"]["schema"] is _SCHEMA  # type: ignore[index]
    )
    assert captured["temperature"] == 0.0
    assert captured["model"] == f"openai/{_settings().default_model}"


def test_generate_structured_resolves_model_hint() -> None:
    adapter = LiteLLMAdapter(settings=_settings())
    captured: dict[str, object] = {}

    async def fake(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _response('{"intent": "x"}', model="gpt-4o-mini")

    with patch(_ACOMPLETION, new=fake):
        _generate(adapter, _request(model_hint="gpt-4o-mini"))

    assert captured["model"] == "openai/gpt-4o-mini"


def test_generate_structured_rejects_non_json_content() -> None:
    """D134 (S47): parse failure surfaces as StructuredOutputParseFailure."""
    adapter = LiteLLMAdapter(settings=_settings())

    async def fake(**kwargs: object) -> SimpleNamespace:
        return _response("not json at all")

    with patch(_ACOMPLETION, new=fake):
        with pytest.raises(
            StructuredOutputParseFailure, match="not valid JSON"
        ) as exc_info:
            _generate(adapter, _request())
    assert exc_info.value.raw_content == "not json at all"


def test_generate_structured_rejects_non_object_json() -> None:
    """D134 (S47): non-object JSON also surfaces as StructuredOutputParseFailure."""
    adapter = LiteLLMAdapter(settings=_settings())

    async def fake(**kwargs: object) -> SimpleNamespace:
        return _response('["a", "list", "not", "an", "object"]')

    with patch(_ACOMPLETION, new=fake):
        with pytest.raises(
            StructuredOutputParseFailure, match="must be a JSON object"
        ) as exc_info:
            _generate(adapter, _request())
    assert exc_info.value.raw_content == '["a", "list", "not", "an", "object"]'


def test_generate_structured_maps_bad_request_to_configuration_error() -> None:
    adapter = LiteLLMAdapter(settings=_settings())

    async def fake(**kwargs: object) -> SimpleNamespace:
        raise BadRequestError("schema rejected", "litellm", "qwen")

    with patch(_ACOMPLETION, new=fake):
        with pytest.raises(InferenceConfigurationError):
            _generate(adapter, _request())


def test_generate_structured_maps_timeout() -> None:
    adapter = LiteLLMAdapter(settings=_settings())

    async def fake(**kwargs: object) -> SimpleNamespace:
        raise Timeout("slow", "litellm", "qwen")

    with patch(_ACOMPLETION, new=fake):
        with pytest.raises(InferenceTimeout):
            _generate(adapter, _request())


def test_adapter_satisfies_structured_output_port() -> None:
    adapter = LiteLLMAdapter(settings=_settings())
    assert isinstance(adapter, StructuredOutputPort)
