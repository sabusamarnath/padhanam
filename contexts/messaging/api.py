"""Public api facade for the messaging context (D17).

Per D17 every context exposes a single ``api.py`` at its root as the
legitimate cross-context import target. Other contexts MUST go through
this surface for any read of the messaging context's
domain/application/ports types; direct imports from
``contexts.messaging.{domain,application,ports}`` from another
context's modules violate the ``contexts-independent-*`` import-linter
contracts.

Surface exposed at P14, S51 (added for the audit-conversation
ConversationFlow implementer's consumption of PendingClarification
machinery per D134/D139):

- ``PendingClarification`` value object (the cross-cutting multi-turn
  state entity at D134).
- ``PendingClarificationReader`` consumer-port Protocol (the
  read-side surface for active-pending lookup at turn-open).
- ``PendingClarificationRepository`` producer-port Protocol (the
  write-side surface for persistence).
- The three lifecycle use cases (``create_pending_clarification``,
  ``resolve_pending_clarification``, ``expire_pending_clarification``).

The ``ignore_imports`` clause at ``.importlinter`` exempts the
``messaging.api -> messaging.{domain,application,ports}`` edge from
the cross-context independence check; the api re-export is the
architectural seam D17 names.
"""

from __future__ import annotations

from contexts.messaging.application.create_pending_clarification import (
    create_pending_clarification,
)
from contexts.messaging.application.expire_pending_clarification import (
    expire_pending_clarification,
)
from contexts.messaging.application.ports.pending_clarification_reader import (
    PendingClarificationReader,
)
from contexts.messaging.application.resolve_pending_clarification import (
    resolve_pending_clarification,
)
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
)
from contexts.messaging.ports.pending_clarification_repository import (
    PendingClarificationRepository,
)

__all__ = [
    "PendingClarification",
    "PendingClarificationReader",
    "PendingClarificationRepository",
    "create_pending_clarification",
    "expire_pending_clarification",
    "resolve_pending_clarification",
]
