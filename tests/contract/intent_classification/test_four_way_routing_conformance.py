"""Five-way meta-classifier routing conformance (D140, P15, S55b-2, S56b).

Binds the five-way routing single-source-of-truth structurally: the five
real ConversationFlow surfaces must be registered coherently across every
routing surface — the CellIdentifier enum, the meta-classifier schema
enum the LLM is constrained to, the dispatch_clarification resolution
lexicon, and the INTENT_CLASSES dispatch-target set the gold set scores
against. A surface registered in one place but missing in another is the
silent-drift this contract catches at CI rather than at a dispatch miss.

``dispatch_clarification`` is the routing sentinel, not a real cell: it is
a CellIdentifier value and a lexicon target but is deliberately absent
from the meta-classifier schema enum (the model must never return it).
"""

from __future__ import annotations

from contexts.intent_classification_evaluation.domain.gold_set import (
    INTENT_CLASSES,
)
from contexts.messaging.application.dispatch_inbound import (
    _DISPATCH_CLARIFICATION_LEXICON,
)
from contexts.messaging.domain.cell_identifier import CellIdentifier
from shared_kernel.meta_classification import META_CLASSIFIER_SCHEMA

_REAL_CELLS = {
    CellIdentifier.MANUAL_ENTRY,
    CellIdentifier.AUDIT_CONVERSATION,
    CellIdentifier.MIRROR_CONVERSATION,
    CellIdentifier.CALENDAR_CONVERSATION,
    CellIdentifier.EMAIL_CONVERSATION,
}


def test_meta_classifier_schema_enum_is_the_real_cells() -> None:
    """The schema's cell_identifier enum is exactly the five real cells.

    The sentinel ``dispatch_clarification`` is excluded (the model must
    not return it; the dispatch layer assigns it).
    """
    schema_enum = set(
        META_CLASSIFIER_SCHEMA["properties"]["cell_identifier"]["enum"]
    )
    assert schema_enum == {c.value for c in _REAL_CELLS}


def test_dispatch_lexicon_covers_all_real_cells() -> None:
    """Every real cell is a resolvable target in the clarification lexicon."""
    lexicon_targets = set(_DISPATCH_CLARIFICATION_LEXICON.values())
    assert _REAL_CELLS.issubset(lexicon_targets)


def test_calendar_conversation_registered_across_all_routing_surfaces() -> None:
    """The fourth route is coherently registered everywhere (S55b-2)."""
    assert CellIdentifier.CALENDAR_CONVERSATION.value == "calendar_conversation"
    assert (
        "calendar_conversation"
        in META_CLASSIFIER_SCHEMA["properties"]["cell_identifier"]["enum"]
    )
    assert (
        CellIdentifier.CALENDAR_CONVERSATION
        in _DISPATCH_CLARIFICATION_LEXICON.values()
    )
    # The gold set scores routing against INTENT_CLASSES dispatch targets.
    assert "calendar_conversation" in INTENT_CLASSES


def test_email_conversation_registered_across_all_routing_surfaces() -> None:
    """The fifth route is coherently registered everywhere (S56b)."""
    assert CellIdentifier.EMAIL_CONVERSATION.value == "email_conversation"
    assert (
        "email_conversation"
        in META_CLASSIFIER_SCHEMA["properties"]["cell_identifier"]["enum"]
    )
    assert (
        CellIdentifier.EMAIL_CONVERSATION
        in _DISPATCH_CLARIFICATION_LEXICON.values()
    )
    # The gold set scores routing against INTENT_CLASSES dispatch targets.
    assert "email_conversation" in INTENT_CLASSES


def test_cell_identifier_real_cells_plus_sentinel() -> None:
    """CellIdentifier carries the five real cells plus the sentinel only."""
    assert set(CellIdentifier) == _REAL_CELLS | {
        CellIdentifier.DISPATCH_CLARIFICATION
    }
