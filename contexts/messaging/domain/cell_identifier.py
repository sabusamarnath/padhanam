"""CellIdentifier enum — single source of truth for ConversationFlow cell names (D140, S52).

D140's meta-classifier dispatch substrate routes inbound messages to
the registered ConversationFlow implementer the classifier names. The
identifier is also the value PendingClarification.target_cell stores
(per D140 and per ``contexts/messaging/domain/pending_clarification.py``'s
``KNOWN_TARGET_CELLS`` invariant).

The enum holds the four identifiers at P14 close. Future ConversationFlow
implementers at P15+ extend the enum additively. There are three categories
(D194). The **meta-routable** cells (``MANUAL_ENTRY``, ``AUDIT_CONVERSATION``,
``MIRROR_CONVERSATION``, ``CALENDAR_CONVERSATION``, ``EMAIL_CONVERSATION``)
name real cells the meta-classifier can route an inbound to. The **routing
sentinel** ``DISPATCH_CLARIFICATION`` is the synthetic identifier the meta-
classification PendingClarification carries when the dispatch flow's Step 5
fires (low classifier confidence; the clarification asks the user to
disambiguate, and the dispatch layer itself handles the routing on the next
inbound). The **pending-only (outbound-initiated)** cell ``CHECKIN`` (D194,
S97b) is a real cell with a runner, but the DAILY_SCHEDULED composer creates
its pending and the reply routes by the active-pending path (D140) — so the
meta-classifier must never emit it and the dispatch lexicon must never resolve
to it (it is deliberately absent from both, like the sentinel, but unlike the
sentinel it has a runner).

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from enum import Enum


class CellIdentifier(str, Enum):
    """The ConversationFlow cells (D140, D194).

    Meta-routable cells plus the dispatch sentinel plus the pending-only
    ``CHECKIN`` cell. See ``test_four_way_routing_conformance`` for the
    category invariants enforced across the routing surfaces.
    """

    MANUAL_ENTRY = "manual_entry"
    AUDIT_CONVERSATION = "audit_conversation"
    MIRROR_CONVERSATION = "mirror_conversation"
    CALENDAR_CONVERSATION = "calendar_conversation"
    EMAIL_CONVERSATION = "email_conversation"
    DISPATCH_CLARIFICATION = "dispatch_clarification"
    CHECKIN = "checkin"


__all__ = ["CellIdentifier"]
