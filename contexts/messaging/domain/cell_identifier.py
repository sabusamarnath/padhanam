"""CellIdentifier enum — single source of truth for ConversationFlow cell names (D140, S52).

D140's meta-classifier dispatch substrate routes inbound messages to
the registered ConversationFlow implementer the classifier names. The
identifier is also the value PendingClarification.target_cell stores
(per D140 and per ``contexts/messaging/domain/pending_clarification.py``'s
``KNOWN_TARGET_CELLS`` invariant).

The enum holds the four identifiers at P14 close. Future ConversationFlow
implementers at P15+ extend the enum additively. The
``MANUAL_ENTRY``, ``AUDIT_CONVERSATION``, and ``MIRROR_CONVERSATION``
values name real cells; ``DISPATCH_CLARIFICATION`` is the synthetic
identifier the meta-classification PendingClarification carries when
the dispatch flow's Step 5 fires (low classifier confidence; the
clarification asks the user to disambiguate, and the dispatch layer
itself handles the routing on the next inbound).

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from enum import Enum


class CellIdentifier(str, Enum):
    """The cells the meta-classifier dispatch can route to (D140)."""

    MANUAL_ENTRY = "manual_entry"
    AUDIT_CONVERSATION = "audit_conversation"
    MIRROR_CONVERSATION = "mirror_conversation"
    DISPATCH_CLARIFICATION = "dispatch_clarification"


__all__ = ["CellIdentifier"]
