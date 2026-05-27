"""Unit tests for MirrorConversationResponse + cell_payload helpers (P14, S52, D141)."""

from __future__ import annotations

from uuid import UUID, uuid4

from contexts.mirror_conversation.application.response import (
    MirrorConversationResponse,
    extract_focus_from_cell_payload,
    serialise_focus_to_cell_payload,
)
from shared_kernel.conversation_flow import ArtefactCitation, CitedResponse


def test_mirror_response_satisfies_cited_response_protocol() -> None:
    """D138 structural enforcement."""
    response = MirrorConversationResponse(
        text="hello",
        cited_artefacts=(
            ArtefactCitation(artefact_id=uuid4(), artefact_type="case"),
        ),
    )
    assert isinstance(response, CitedResponse)


def test_has_citations_true_when_artefacts_present() -> None:
    response = MirrorConversationResponse(
        text="hello",
        cited_artefacts=(
            ArtefactCitation(artefact_id=uuid4(), artefact_type="case"),
        ),
    )
    assert response.has_citations


def test_has_citations_false_when_all_tuples_empty() -> None:
    response = MirrorConversationResponse(text="clarification")
    assert not response.has_citations


def test_has_focus_true_when_focus_set() -> None:
    response = MirrorConversationResponse(
        text="hello",
        current_focus_artefact=ArtefactCitation(
            artefact_id=uuid4(), artefact_type="case"
        ),
    )
    assert response.has_focus


def test_has_focus_false_when_focus_absent() -> None:
    response = MirrorConversationResponse(text="hello")
    assert not response.has_focus


def test_serialise_focus_round_trips_through_extract() -> None:
    artefact_id = uuid4()
    focus = ArtefactCitation(artefact_id=artefact_id, artefact_type="data_point")
    payload = serialise_focus_to_cell_payload(focus)
    assert payload == {
        "current_focus_artefact": {
            "artefact_id": str(artefact_id),
            "artefact_type": "data_point",
        }
    }
    extracted = extract_focus_from_cell_payload(payload)
    assert extracted == focus


def test_extract_focus_returns_none_for_missing_payload() -> None:
    assert extract_focus_from_cell_payload(None) is None
    assert extract_focus_from_cell_payload({}) is None


def test_extract_focus_returns_none_for_malformed_payload() -> None:
    """Implementer-side validation per D141."""
    assert (
        extract_focus_from_cell_payload({"current_focus_artefact": "not a dict"})
        is None
    )
    assert (
        extract_focus_from_cell_payload(
            {"current_focus_artefact": {"artefact_id": "not-a-uuid"}}
        )
        is None
    )
    assert (
        extract_focus_from_cell_payload(
            {"current_focus_artefact": {
                "artefact_id": str(uuid4()),
                "artefact_type": "",
            }}
        )
        is None
    )


def test_extract_focus_returns_none_for_unrelated_payload_shape() -> None:
    """A payload from a different ConversationFlow implementer routes as no-prior."""
    assert (
        extract_focus_from_cell_payload({"some_other_key": "value"}) is None
    )
