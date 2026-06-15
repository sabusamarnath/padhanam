"""Routing conformance across cell categories (D140, D194, P15, S55b-2, S56b, S97b).

Binds the routing single-source-of-truth structurally. There are three cell
categories (D194):

- **meta-routable cells** — the real ConversationFlow surfaces the meta-
  classifier can route an inbound to. Registered coherently across the
  CellIdentifier enum, the meta-classifier schema enum the LLM is constrained
  to, the dispatch_clarification resolution lexicon, and the INTENT_CLASSES
  dispatch-target set the gold set scores against.
- the **routing sentinel** ``dispatch_clarification`` — a CellIdentifier value
  and a lexicon target, deliberately absent from the meta-classifier schema
  enum (the model must never return it).
- **pending-only (outbound-initiated) cells** — real cells with runners that
  are never meta-routed (``checkin``, S97b): the composer creates their
  pending and the reply routes by the active-pending path. They are present in
  the identity surfaces (CellIdentifier, the target_cell DB constraint,
  KNOWN_TARGET_CELLS) but **absent** from every meta-routing surface (the
  meta-classifier schema, the dispatch lexicon, INTENT_CLASSES) — so the model
  can never route a user to an outbound-only surface.

A surface registered in one place but missing in another (or present in a
meta-routing surface it must stay out of) is the silent drift this contract
catches at CI rather than at a dispatch miss.
"""

from __future__ import annotations

from contexts.intent_classification_evaluation.domain.gold_set import (
    INTENT_CLASSES,
)
from contexts.messaging.application.dispatch_inbound import (
    _DISPATCH_CLARIFICATION_LEXICON,
)
from contexts.messaging.domain.cell_identifier import CellIdentifier
from contexts.messaging.domain.pending_clarification import KNOWN_TARGET_CELLS
from shared_kernel.meta_classification import META_CLASSIFIER_SCHEMA

# The meta-routable real cells (the meta-classifier can return any of these).
_META_ROUTABLE_CELLS = {
    CellIdentifier.MANUAL_ENTRY,
    CellIdentifier.AUDIT_CONVERSATION,
    CellIdentifier.MIRROR_CONVERSATION,
    CellIdentifier.CALENDAR_CONVERSATION,
    CellIdentifier.EMAIL_CONVERSATION,
}

# The pending-only (outbound-initiated) cells (D194) — real cells, never
# meta-routed. The composer creates the pending; the reply routes by the
# active-pending path.
_PENDING_ONLY_CELLS = {
    CellIdentifier.CHECKIN,
}


def test_meta_classifier_schema_enum_is_the_meta_routable_cells() -> None:
    """The schema's cell_identifier enum is exactly the meta-routable cells.

    The sentinel ``dispatch_clarification`` is excluded (the model must not
    return it; the dispatch layer assigns it), and the pending-only cells are
    excluded (the model must never route a user to an outbound-only surface).
    """
    schema_enum = set(
        META_CLASSIFIER_SCHEMA["properties"]["cell_identifier"]["enum"]
    )
    assert schema_enum == {c.value for c in _META_ROUTABLE_CELLS}


def test_dispatch_lexicon_covers_all_meta_routable_cells() -> None:
    """Every meta-routable cell is a resolvable target in the lexicon."""
    lexicon_targets = set(_DISPATCH_CLARIFICATION_LEXICON.values())
    assert _META_ROUTABLE_CELLS.issubset(lexicon_targets)


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


def test_cell_identifier_is_the_three_categories() -> None:
    """CellIdentifier carries exactly the three categories (D194).

    Meta-routable cells, the dispatch sentinel, and the pending-only cells —
    nothing else.
    """
    assert set(CellIdentifier) == (
        _META_ROUTABLE_CELLS
        | {CellIdentifier.DISPATCH_CLARIFICATION}
        | _PENDING_ONLY_CELLS
    )


def test_pending_only_cells_present_in_identity_surfaces() -> None:
    """A pending-only cell owns a pending, so it must be admitted by the
    identity surfaces — the CellIdentifier enum and the KNOWN_TARGET_CELLS set
    (and, via the constraint-sync tripwire, the DB target_cell constraint)."""
    for cell in _PENDING_ONLY_CELLS:
        assert cell in CellIdentifier
        assert cell.value in KNOWN_TARGET_CELLS


def test_pending_only_cells_absent_from_every_meta_routing_surface() -> None:
    """A pending-only cell (D194) is outbound-initiated, so the meta-classifier
    must never emit it, the dispatch lexicon must never resolve to it, and it is
    not an inbound intent class. Absence here is the safety property: the model
    cannot route a user to an outbound-only surface."""
    schema_enum = set(
        META_CLASSIFIER_SCHEMA["properties"]["cell_identifier"]["enum"]
    )
    lexicon_targets = set(_DISPATCH_CLARIFICATION_LEXICON.values())
    for cell in _PENDING_ONLY_CELLS:
        assert cell.value not in schema_enum
        assert cell not in lexicon_targets
        assert cell.value not in INTENT_CLASSES
