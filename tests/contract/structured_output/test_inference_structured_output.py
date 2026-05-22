"""Registers the inference LiteLLM adapter against the StructuredOutputPort contract.

The inference adapter is the first StructuredOutputPort implementer
(S45, D130) — it gained ``generate_structured`` as an additive
extension. This module builds a fresh-adapter factory and registers
it through the conftest mechanism, so the parametrised scenarios in
``test_structured_output_contract.py`` run against it automatically.
A future implementer (P14 calendar-read / email-read parsing, the
methodology library) adds an equivalent
``test_<implementer>_structured_output.py`` and needs no harness
change.

Adapter construction performs no I/O — it only stores the settings
object — so a synthetic master key suffices for the structural
conformance scenarios.
"""

from __future__ import annotations

from contexts.inference.adapters.outbound.litellm import LiteLLMAdapter
from padhanam.config import InferenceSettings
from shared_kernel.structured_output import StructuredOutputPort

from tests.contract.structured_output.conftest import (
    StructuredOutputImplementerFixture,
    register_structured_output_implementer,
)


def _make_adapter() -> LiteLLMAdapter:
    """A fresh LiteLLM adapter; construction stores settings only."""
    return LiteLLMAdapter(
        settings=InferenceSettings(
            litellm_master_key="sk-structured-output-harness"
        )
    )


register_structured_output_implementer(
    StructuredOutputImplementerFixture(
        name="inference.LiteLLMAdapter",
        implementer_cls=LiteLLMAdapter,
        make_instance=_make_adapter,
    )
)


def test_inference_adapter_satisfies_runtime_checkable_port() -> None:
    """Sanity check: the inference adapter structurally satisfies the
    ``@runtime_checkable`` StructuredOutputPort. The parametrised
    scenarios in ``test_structured_output_contract.py`` verify the rest."""
    assert isinstance(_make_adapter(), StructuredOutputPort)
