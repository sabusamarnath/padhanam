"""Unit tests for the ConversationFlow Protocol and value objects (D115, S45; D138, S51)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from shared_kernel.conversation_flow import (
    ArtefactCitation,
    CitedResponse,
    ConversationClosure,
    ConversationFlow,
    ConversationInput,
    ConversationInvocation,
    ConversationOutcome,
    ConversationState,
)


def test_value_objects_construct() -> None:
    invocation = ConversationInvocation(purpose="audit-review", actor_id="op")
    state = ConversationState(
        conversation_id="c1", purpose="audit-review", turn_count=0,
        is_open=True,
    )
    user_input = ConversationInput(text="why was this surfaced?")
    closure = ConversationClosure(reason="user-satisfied")
    outcome = ConversationOutcome(
        conversation_id="c1", turn_count=2, resolution="resolved"
    )
    assert invocation.purpose == "audit-review"
    assert state.is_open is True
    assert state.turn_count == 0
    assert user_input.text == "why was this surfaced?"
    assert closure.reason == "user-satisfied"
    assert outcome.resolution == "resolved"


def test_open_slots_default_to_fresh_dicts() -> None:
    one = ConversationInvocation(purpose="p", actor_id="a")
    two = ConversationInvocation(purpose="p", actor_id="a")
    assert one.parameters == {}
    # each instance gets an independent dict, not a shared default
    assert one.parameters is not two.parameters
    state = ConversationState(
        conversation_id="c", purpose="p", turn_count=0, is_open=True
    )
    assert state.payload == {}
    assert ConversationInput(text="t").metadata == {}
    assert ConversationOutcome(
        conversation_id="c", turn_count=1, resolution="r"
    ).payload == {}


def test_value_objects_are_frozen() -> None:
    state = ConversationState(
        conversation_id="c", purpose="p", turn_count=0, is_open=True
    )
    with pytest.raises(FrozenInstanceError):
        state.turn_count = 1  # type: ignore[misc]


class _ConformingFlow:
    async def open(
        self, invocation: ConversationInvocation
    ) -> ConversationState:
        return ConversationState(
            conversation_id="c", purpose=invocation.purpose,
            turn_count=0, is_open=True,
        )

    async def turn(
        self, state: ConversationState, user_input: ConversationInput
    ) -> ConversationState:
        return state

    async def close(
        self, state: ConversationState, closure: ConversationClosure
    ) -> ConversationOutcome:
        return ConversationOutcome(
            conversation_id=state.conversation_id,
            turn_count=state.turn_count, resolution=closure.reason,
        )


class _MissingClose:
    async def open(self, invocation: object) -> object: ...

    async def turn(self, state: object, user_input: object) -> object: ...


def test_conversation_flow_is_runtime_checkable() -> None:
    assert isinstance(_ConformingFlow(), ConversationFlow)


def test_non_conforming_class_fails_isinstance() -> None:
    assert not isinstance(_MissingClose(), ConversationFlow)


def test_artefact_citation_constructs_and_freezes() -> None:
    citation = ArtefactCitation(artefact_id=uuid4(), artefact_type="case")
    assert citation.artefact_type == "case"
    with pytest.raises(FrozenInstanceError):
        citation.artefact_type = "data_point"  # type: ignore[misc]


def test_artefact_citation_rejects_empty_discriminator() -> None:
    with pytest.raises(ValueError, match="artefact_type"):
        ArtefactCitation(artefact_id=uuid4(), artefact_type="")


def test_artefact_citation_accepts_meeting_discriminator() -> None:
    citation = ArtefactCitation(artefact_id=uuid4(), artefact_type="meeting")
    assert citation.artefact_type == "meeting"


def test_artefact_citation_rejects_unknown_discriminator() -> None:
    with pytest.raises(ValueError, match="artefact_type"):
        ArtefactCitation(artefact_id=uuid4(), artefact_type="widget")


def test_cited_response_is_runtime_checkable_against_conforming_object() -> None:
    from dataclasses import dataclass, field
    from uuid import UUID as _UUID

    @dataclass(frozen=True)
    class _Conforming:
        cited_intake_records: tuple[_UUID, ...] = field(default_factory=tuple)
        cited_audit_events: tuple[_UUID, ...] = field(default_factory=tuple)
        cited_artefacts: tuple[ArtefactCitation, ...] = field(default_factory=tuple)

    assert isinstance(_Conforming(), CitedResponse)


def test_cited_response_fails_isinstance_on_missing_field() -> None:
    from dataclasses import dataclass, field
    from uuid import UUID as _UUID

    @dataclass(frozen=True)
    class _MissingArtefacts:
        cited_intake_records: tuple[_UUID, ...] = field(default_factory=tuple)
        cited_audit_events: tuple[_UUID, ...] = field(default_factory=tuple)
        # cited_artefacts absent

    assert not isinstance(_MissingArtefacts(), CitedResponse)
