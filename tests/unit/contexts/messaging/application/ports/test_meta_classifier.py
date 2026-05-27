"""Unit tests for MetaClassifier port + result value object (D140, S52)."""

from __future__ import annotations

import pytest

from contexts.messaging.application.ports.meta_classifier import (
    ConversationTurn,
    MetaClassificationResult,
    MetaClassifier,
)
from contexts.messaging.domain.cell_identifier import CellIdentifier


def test_conversation_turn_constructs_with_valid_role() -> None:
    turn = ConversationTurn(role="user", text="hello")
    assert turn.role == "user"
    assert turn.text == "hello"


def test_conversation_turn_rejects_invalid_role() -> None:
    with pytest.raises(ValueError, match="role"):
        ConversationTurn(role="system", text="hi")


def test_conversation_turn_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="text"):
        ConversationTurn(role="user", text="")


def test_meta_classification_result_constructs() -> None:
    result = MetaClassificationResult(
        cell_identifier=CellIdentifier.MANUAL_ENTRY,
        confidence=0.85,
    )
    assert result.cell_identifier is CellIdentifier.MANUAL_ENTRY
    assert result.confidence == 0.85


def test_meta_classification_result_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        MetaClassificationResult(
            cell_identifier=CellIdentifier.MANUAL_ENTRY,
            confidence=1.5,
        )


def test_protocol_isinstance_admits_minimal_adapter() -> None:
    class _Stub:
        async def classify(
            self,
            *,
            tenant_id,
            inbound_text,
            conversation_history=(),
        ):
            return MetaClassificationResult(
                cell_identifier=CellIdentifier.MANUAL_ENTRY,
                confidence=1.0,
            )

    assert isinstance(_Stub(), MetaClassifier)
