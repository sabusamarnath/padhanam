"""Parametrised conformance scenarios for the ConversationFlow Protocol (D115).

Runs against every implementer registered through the conftest
mechanism. Each scenario exercises a contract property
``@runtime_checkable`` cannot verify — the minimum callable
signatures and the open / turn / close lifecycle semantics the
Protocol docstring commits. Scenarios use only the Protocol's
declared surface.

The five scenarios map to five contract properties: signature,
lifecycle, append-only turns, closure semantics, and cross-context
type invariance.

S46 registers the first implementer — the manual entry cell — so the
five parametrised scenarios now run. ``test_manual_entry_cell_is_registered``
is the non-parametrised check that the first implementer is in place;
P14's audit-conversation and mirror-conversation implementers join it.
"""

from __future__ import annotations

import asyncio
import inspect

from shared_kernel.conversation_flow import (
    ConversationFlow,
    ConversationOutcome,
    ConversationState,
)

from tests.contract.conversation_flow.conftest import (
    _REGISTRY,
    ConversationFlowImplementerFixture,
    _load_registration_modules,
    register_conversation_flow_implementer,
)


def test_manual_entry_cell_is_registered() -> None:
    """S46 registers the manual entry cell as the first ConversationFlow
    implementer (D115); the five parametrised scenarios below run
    against it. P14's audit-conversation (5.1) and mirror-conversation
    (4.1) implementers add their own ``test_<name>_conversation_flow.py``
    registration module and join the parametrised set with no harness
    change."""
    _load_registration_modules()
    assert callable(register_conversation_flow_implementer)
    assert "manual_entry_cell" in [f.name for f in _REGISTRY]


def test_lifecycle_method_signatures(
    conversation_flow_implementer: ConversationFlowImplementerFixture,
) -> None:
    """Signature scenario: ``open`` / ``turn`` / ``close`` are async and
    present the Protocol's parameter shapes; any parameter beyond the
    declared ones carries a default so the Protocol call stays valid."""
    cls = conversation_flow_implementer.implementer_cls
    assert isinstance(conversation_flow_implementer.make_instance(), ConversationFlow)
    for method_name, required in (("open", 1), ("turn", 2), ("close", 2)):
        method = getattr(cls, method_name)
        assert inspect.iscoroutinefunction(method), (
            f"{method_name} must be async"
        )
        params = list(inspect.signature(method).parameters.values())[1:]
        assert len(params) >= required, (
            f"{method_name} must accept at least {required} argument(s)"
        )
        for extra in params[required:]:
            assert extra.default is not inspect.Parameter.empty


def test_open_yields_fresh_state(
    conversation_flow_implementer: ConversationFlowImplementerFixture,
) -> None:
    """Lifecycle scenario: ``open`` returns a ConversationState that is
    open and carries turn_count 0 — a freshly-started conversation."""
    instance = conversation_flow_implementer.make_instance()
    state = asyncio.run(
        instance.open(conversation_flow_implementer.sample_invocation)
    )
    assert isinstance(state, ConversationState)
    assert state.is_open is True
    assert state.turn_count == 0


def test_turn_advances_count_monotonically(
    conversation_flow_implementer: ConversationFlowImplementerFixture,
) -> None:
    """Append-only-turns scenario: each ``turn`` advances ``turn_count``
    by exactly one, monotonically, and the ``conversation_id`` is stable
    across turns."""
    instance = conversation_flow_implementer.make_instance()

    async def _drive() -> tuple[ConversationState, ConversationState]:
        opened = await instance.open(
            conversation_flow_implementer.sample_invocation
        )
        first = await instance.turn(
            opened, conversation_flow_implementer.sample_input
        )
        second = await instance.turn(
            first, conversation_flow_implementer.sample_input
        )
        return first, second

    first, second = asyncio.run(_drive())
    assert first.turn_count == 1
    assert second.turn_count == 2
    assert first.conversation_id == second.conversation_id


def test_close_yields_terminal_outcome(
    conversation_flow_implementer: ConversationFlowImplementerFixture,
) -> None:
    """Closure-semantics scenario: ``close`` returns a ConversationOutcome
    carrying the conversation's id — the terminal record of the exchange."""
    instance = conversation_flow_implementer.make_instance()

    async def _drive() -> tuple[ConversationState, ConversationOutcome]:
        opened = await instance.open(
            conversation_flow_implementer.sample_invocation
        )
        outcome = await instance.close(
            opened, conversation_flow_implementer.sample_closure
        )
        return opened, outcome

    opened, outcome = asyncio.run(_drive())
    assert isinstance(outcome, ConversationOutcome)
    assert outcome.conversation_id == opened.conversation_id


def test_lifecycle_returns_shared_kernel_types(
    conversation_flow_implementer: ConversationFlowImplementerFixture,
) -> None:
    """Cross-context-invariance scenario: ``open`` / ``turn`` return the
    shared_kernel ConversationState and ``close`` returns the
    shared_kernel ConversationOutcome — exactly, not a context-specific
    subtype. The Protocol's value objects are referentially shared."""
    instance = conversation_flow_implementer.make_instance()

    async def _drive() -> tuple[object, object, object]:
        opened = await instance.open(
            conversation_flow_implementer.sample_invocation
        )
        turned = await instance.turn(
            opened, conversation_flow_implementer.sample_input
        )
        outcome = await instance.close(
            turned, conversation_flow_implementer.sample_closure
        )
        return opened, turned, outcome

    opened, turned, outcome = asyncio.run(_drive())
    assert type(opened) is ConversationState
    assert type(turned) is ConversationState
    assert type(outcome) is ConversationOutcome
