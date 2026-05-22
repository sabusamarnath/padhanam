"""Parametrised conformance scenarios for StructuredOutputPort (D130).

Runs against every implementer registered through the conftest
mechanism. The scenarios verify structural conformance — that
``generate_structured`` is async and presents the Protocol's
request-in / response-out signature — properties ``@runtime_checkable``
does not check. The behavioural contract (a schema-conforming
response value) is a live-model concern and is out of scope for the
default, offline test tier.

The inference LiteLLM adapter is the first implementer (S45); a P14
structured-output consumer adds a registration module and is
auto-checked with no harness change.
"""

from __future__ import annotations

import inspect

from shared_kernel.structured_output import StructuredOutputPort

from tests.contract.structured_output.conftest import (
    _REGISTRY,
    StructuredOutputImplementerFixture,
)


def test_harness_has_at_least_one_implementer() -> None:
    """The StructuredOutputPort harness carries the inference adapter at
    S45 — the registration mechanism is exercised, not merely declared."""
    names = {f.name for f in _REGISTRY}
    assert "inference.LiteLLMAdapter" in names


def test_implementer_satisfies_structured_output_port(
    structured_output_implementer: StructuredOutputImplementerFixture,
) -> None:
    """Membership scenario: the implementer structurally satisfies the
    ``@runtime_checkable`` StructuredOutputPort protocol."""
    assert isinstance(
        structured_output_implementer.make_instance(), StructuredOutputPort
    )


def test_generate_structured_is_async(
    structured_output_implementer: StructuredOutputImplementerFixture,
) -> None:
    """Async scenario: ``generate_structured`` is a coroutine function —
    the Protocol declares it ``async`` so callers can await an LLM call."""
    method = structured_output_implementer.implementer_cls.generate_structured
    assert inspect.iscoroutinefunction(method)


def test_generate_structured_minimum_signature(
    structured_output_implementer: StructuredOutputImplementerFixture,
) -> None:
    """Signature scenario: ``generate_structured`` accepts the request
    argument the Protocol declares; any parameter beyond it carries a
    default so the single-argument Protocol call stays valid."""
    method = structured_output_implementer.implementer_cls.generate_structured
    params = list(inspect.signature(method).parameters.values())[1:]
    assert len(params) >= 1, (
        "generate_structured must accept a StructuredOutputRequest"
    )
    for extra in params[1:]:
        assert extra.default is not inspect.Parameter.empty, (
            f"generate_structured parameter {extra.name!r} beyond the "
            "request must carry a default to stay Protocol-compatible"
        )


def test_generate_structured_returns_structured_output_response(
    structured_output_implementer: StructuredOutputImplementerFixture,
) -> None:
    """Return-type scenario: ``generate_structured`` declares a
    StructuredOutputResponse return — the Protocol's response shape."""
    method = structured_output_implementer.implementer_cls.generate_structured
    return_annotation = inspect.signature(method).return_annotation
    assert "StructuredOutputResponse" in str(return_annotation)
