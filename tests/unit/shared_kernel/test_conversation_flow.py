"""Unit tests for the ConversationFlow Protocol and value objects (D115, S45)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from shared_kernel.conversation_flow import (
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
