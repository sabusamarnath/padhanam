"""Unit tests for the MetaClassifier adapters (D140, S52)."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from contexts.messaging.adapters.llm_meta_classifier import (
    LlmMetaClassifierAdapter,
)
from contexts.messaging.adapters.rule_based_meta_classifier import (
    RuleBasedMetaClassifierAdapter,
)
from contexts.messaging.application.ports.meta_classifier import (
    ConversationTurn,
    MetaClassificationResult,
)
from contexts.messaging.domain.cell_identifier import CellIdentifier
from shared_kernel import StructuredOutputResponse


# ---------------------------------------------- rule-based adapter


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_rule_based_routes_manual_entry_on_add() -> None:
    adapter = RuleBasedMetaClassifierAdapter()
    result = _run(
        adapter.classify(
            tenant_id=uuid4(),
            inbound_text="Add a data point for Q3 revenue: 5M",
        )
    )
    assert result.cell_identifier is CellIdentifier.MANUAL_ENTRY
    assert result.confidence >= 0.5


def test_rule_based_routes_audit_on_history_query() -> None:
    adapter = RuleBasedMetaClassifierAdapter()
    result = _run(
        adapter.classify(
            tenant_id=uuid4(),
            inbound_text="Show me the audit history for the Q3 review case",
        )
    )
    assert result.cell_identifier is CellIdentifier.AUDIT_CONVERSATION


def test_rule_based_routes_mirror_on_show_case() -> None:
    adapter = RuleBasedMetaClassifierAdapter()
    result = _run(
        adapter.classify(
            tenant_id=uuid4(),
            inbound_text="Show me the Q3 portfolio review",
        )
    )
    assert result.cell_identifier is CellIdentifier.MIRROR_CONVERSATION


def test_rule_based_routes_mirror_on_relative_intent() -> None:
    adapter = RuleBasedMetaClassifierAdapter()
    history = (
        ConversationTurn(
            role="assistant",
            text="Here is the Q3 portfolio review: revenue 5M, churn 2%.",
        ),
    )
    result = _run(
        adapter.classify(
            tenant_id=uuid4(),
            inbound_text="tell me about revenue",
            conversation_history=history,
        )
    )
    assert result.cell_identifier is CellIdentifier.MIRROR_CONVERSATION


def test_rule_based_low_confidence_on_ambiguous() -> None:
    adapter = RuleBasedMetaClassifierAdapter()
    result = _run(
        adapter.classify(
            tenant_id=uuid4(),
            inbound_text="Q3 results",
        )
    )
    # Bare noun phrase matches none of the explicit token sets; the
    # heuristic falls through to low confidence on manual_entry as
    # the safe default per D140 Step 5 routing.
    assert result.confidence < 0.5
    assert result.cell_identifier is CellIdentifier.MANUAL_ENTRY


# ----------------------------------------------- LLM adapter


class _StubStructuredOutput:
    """Stub StructuredOutputPort returning a fixed response."""

    def __init__(self, value: dict[str, Any]) -> None:
        self._value = value

    async def generate_structured(self, request: Any) -> Any:
        return StructuredOutputResponse(
            value=self._value,
            confidence=float(self._value.get("confidence", 0.0)),
            provider_metadata={},
        )


def test_llm_adapter_parses_structured_response() -> None:
    stub = _StubStructuredOutput(
        {"cell_identifier": "audit_conversation", "confidence": 0.92}
    )
    adapter = LlmMetaClassifierAdapter(structured_output_port=stub)
    result = _run(
        adapter.classify(
            tenant_id=uuid4(),
            inbound_text="What happened to my Q3 case yesterday?",
        )
    )
    assert result.cell_identifier is CellIdentifier.AUDIT_CONVERSATION
    assert result.confidence == 0.92


def test_llm_adapter_returns_mirror_at_high_confidence() -> None:
    stub = _StubStructuredOutput(
        {"cell_identifier": "mirror_conversation", "confidence": 0.85}
    )
    adapter = LlmMetaClassifierAdapter(structured_output_port=stub)
    result = _run(
        adapter.classify(
            tenant_id=uuid4(),
            inbound_text="Show me the Q3 portfolio review",
        )
    )
    assert result.cell_identifier is CellIdentifier.MIRROR_CONVERSATION
    assert result.confidence == 0.85


def test_llm_adapter_rejects_unknown_cell_identifier() -> None:
    stub = _StubStructuredOutput(
        {"cell_identifier": "calendar_read", "confidence": 0.95}
    )
    adapter = LlmMetaClassifierAdapter(structured_output_port=stub)
    with pytest.raises(ValueError):
        _run(
            adapter.classify(
                tenant_id=uuid4(),
                inbound_text="Show me my calendar",
            )
        )


def test_llm_adapter_renders_history_into_prompt() -> None:
    """Conversation history must be passed to the LLM via the prompt."""

    captured: dict[str, Any] = {}

    class _CapturingStub:
        async def generate_structured(self, request: Any) -> Any:
            captured["prompt"] = request.prompt
            return StructuredOutputResponse(
                value={
                    "cell_identifier": "mirror_conversation",
                    "confidence": 0.7,
                },
                confidence=0.7,
                provider_metadata={},
            )

    adapter = LlmMetaClassifierAdapter(structured_output_port=_CapturingStub())
    history = (
        ConversationTurn(role="user", text="show me the Q3 review"),
        ConversationTurn(role="assistant", text="Q3 review: revenue 5M"),
    )
    _run(
        adapter.classify(
            tenant_id=uuid4(),
            inbound_text="tell me about revenue",
            conversation_history=history,
        )
    )
    assert "Q3 review: revenue 5M" in captured["prompt"]
    assert "tell me about revenue" in captured["prompt"]
