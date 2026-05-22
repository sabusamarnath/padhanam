"""Parametrised conformance scenarios for the Revisable Protocol (D114, D125).

Runs against every implementer registered through the conftest mechanism.
Each scenario exercises a contract property ``@runtime_checkable`` cannot
verify — the minimum callable signature, the return type, and the
append-only / ordering / genesis semantics the Protocol docstring
commits. Scenarios use only the Protocol's declared surface (``revise``,
``revision_history``); they never reach into an implementer's internals,
so the harness stays valid for every future implementer.

The five scenarios map to the five contract properties: signature,
return type, append-only, ordering, genesis.
"""

from __future__ import annotations

import inspect

from shared_kernel import ActorReference, AssertionChange
from shared_kernel.revisable import Revisable

from tests.contract.revisable.conftest import RevisableImplementerFixture

# revise() takes an ActorReference per the Protocol; the persisted
# authoring identity is irrelevant to the conformance scenarios, so one
# shared actor suffices.
_ACTOR = ActorReference(user_id="revisable-contract-actor")


def _change(seq: int) -> AssertionChange:
    """A distinguishable AssertionChange for the multi-revise scenarios."""
    return AssertionChange(value={"revisable_contract_seq": seq})


def test_revise_minimum_signature(
    revisable_implementer: RevisableImplementerFixture,
) -> None:
    """Signature scenario: ``revise`` presents the Protocol's
    ``(change, actor)`` shape, and any parameter beyond those two carries
    a default so the two-argument call stays valid — the LSP-compatible
    optional-extension shape (DataPoint.revise's ``intake_id`` per D128).
    """
    revise = revisable_implementer.implementer_cls.revise
    params = list(inspect.signature(revise).parameters.values())[1:]  # drop self
    assert len(params) >= 2, "revise must accept at least (change, actor)"
    for extra in params[2:]:
        assert extra.default is not inspect.Parameter.empty, (
            f"revise parameter {extra.name!r} beyond (change, actor) must "
            "carry a default to stay Protocol-compatible"
        )
    # the implementer presents the full Protocol surface (revise plus
    # revision_history) — the membership @runtime_checkable verifies — and
    # the two-argument call is exercised positively.
    instance = revisable_implementer.make_instance()
    assert isinstance(instance, Revisable)
    instance.revise(revisable_implementer.sample_change, _ACTOR)


def test_revise_returns_same_concrete_type(
    revisable_implementer: RevisableImplementerFixture,
) -> None:
    """Return-type scenario: ``revise`` returns an instance of the same
    concrete class — the covariant narrowing of the Protocol's declared
    ``Revisable[RevisionT]`` return."""
    instance = revisable_implementer.make_instance()
    revised = instance.revise(revisable_implementer.sample_change, _ACTOR)
    assert type(revised) is type(instance)


def test_revise_is_append_only(
    revisable_implementer: RevisableImplementerFixture,
) -> None:
    """Append-only scenario: ``revise`` appends exactly one revision and
    does not mutate the original — the original's revision history is
    unchanged after the call."""
    instance = revisable_implementer.make_instance()
    before = instance.revision_history()
    revised = instance.revise(revisable_implementer.sample_change, _ACTOR)
    assert len(revised.revision_history()) == len(before) + 1
    assert instance.revision_history() == before


def test_revision_history_is_ordered_append(
    revisable_implementer: RevisableImplementerFixture,
) -> None:
    """Ordering scenario: sequential ``revise`` calls append at the tail
    in call order. Each step's history is a prefix of the next — entries
    are never reordered or inserted — verified through the Protocol's
    ``revision_history`` surface alone."""
    step0 = revisable_implementer.make_instance()
    step1 = step0.revise(_change(1), _ACTOR)
    step2 = step1.revise(_change(2), _ACTOR)
    step3 = step2.revise(_change(3), _ACTOR)
    h0, h1, h2, h3 = (
        s.revision_history() for s in (step0, step1, step2, step3)
    )
    assert h1[: len(h0)] == h0
    assert h2[: len(h1)] == h1
    assert h3[: len(h2)] == h2
    assert len(h3) == len(h0) + 3


def test_genesis_revision_is_stable(
    revisable_implementer: RevisableImplementerFixture,
) -> None:
    """Genesis scenario: a fresh instance carries a genesis revision; it
    stays at index 0 and is unchanged across subsequent revises — it
    never gains a retroactive predecessor."""
    instance = revisable_implementer.make_instance()
    history = instance.revision_history()
    assert len(history) >= 1, "a fresh instance must carry a genesis revision"
    genesis = history[0]
    step1 = instance.revise(_change(1), _ACTOR)
    step2 = step1.revise(_change(2), _ACTOR)
    assert step1.revision_history()[0] == genesis
    assert step2.revision_history()[0] == genesis
