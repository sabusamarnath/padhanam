"""Cell-facing PendingClarification consumer port (D134, S47).

The manual entry cell consults PendingClarification at turn-open
through this narrow read port. Phase 2-A composition wires the
adapter to the same persistence the create/resolve/expire use cases
consume; the narrow port surface lets cell-unit tests fake the read
without touching the repository or the audit emission discipline.

Sits at ``contexts/messaging/application/ports/`` (sibling of
PortfolioGateway and CellDispatch) per the cell-consumer-port
convention established at S46.

Ports layer is pure per D16 — stdlib plus domain types only.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
)


class PendingClarificationReader(Protocol):
    """Cell-facing read surface for active PendingClarification state."""

    async def get_active(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
    ) -> PendingClarification | None:
        """Return the active PENDING for ``(tenant_id, user_id)`` or None.

        Implementations check expiry: a PENDING whose ``expires_at``
        has already elapsed returns as ``None`` (the cell treats the
        absent state as a fresh turn). The mechanical expiry sweep
        runs at create-time per the D134 invariant; this read
        additionally guards against client-side expiry-window drift.
        """
        ...


__all__ = ["PendingClarificationReader"]
