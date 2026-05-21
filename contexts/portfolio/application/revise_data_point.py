"""revise_data_point use case (D124, D125, D126).

Loads a DataPoint with its revision history, applies the Revisable
Protocol's ``revise`` (which appends a REVISION assertion), persists
the new assertion, and emits a ``portfolio.data_point.revise`` audit
event. Returns the revised DataPoint.

S44a (D126): the use case accepts an ActorContext, applies the
``requires_authorisation`` decorator, extracts ``actor.tenant_context``
for adapter calls, and derives an ``ActorReference`` from
``actor.actor_id``. The Revisable Protocol's ``actor`` parameter
stays ``ActorReference`` — authorisation is enforced at this
decorator before ``revise`` runs, so the shared-kernel revision
contract needs only persisted identity.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from contexts.audit.domain.ports import AuditPort

from contexts.portfolio.application.audit_events import (
    draft_data_point_revise,
)
from contexts.portfolio.domain import DataPoint
from contexts.portfolio.ports import PortfolioReader, PortfolioRepository
from shared_kernel import ActorContext, ActorReference, AssertionChange
from shared_kernel.authorisation import (
    PORTFOLIO_DATA_POINT_REVISE,
    requires_authorisation,
)


class DataPointNotFoundError(Exception):
    """Raised when ``revise_data_point`` targets an unknown data point."""

    def __init__(self, data_point_id: UUID) -> None:
        super().__init__(f"data point {data_point_id} not found")
        self.data_point_id = data_point_id


@requires_authorisation(PORTFOLIO_DATA_POINT_REVISE)
async def revise_data_point(
    *,
    repository: PortfolioRepository,
    reader: PortfolioReader,
    audit_port: AuditPort,
    actor: ActorContext,
    data_point_id: UUID,
    value: dict[str, Any],
) -> DataPoint:
    """Append a revision to a DataPoint; persist and audit it."""
    tenant_context = actor.tenant_context
    authored_by = ActorReference(user_id=actor.actor_id)
    existing = await reader.get_data_point(
        tenant_context=tenant_context, data_point_id=data_point_id
    )
    if existing is None:
        raise DataPointNotFoundError(data_point_id)
    revised = existing.revise(AssertionChange(value=value), authored_by)
    new_assertion = revised.assertions[-1]
    await repository.save_assertion(
        tenant_context=tenant_context, assertion=new_assertion
    )
    await audit_port.emit(
        draft_data_point_revise(
            tenant_context=tenant_context,
            data_point_id=data_point_id,
            new_assertion=new_assertion,
            actor=authored_by,
        )
    )
    return revised


__all__ = ["DataPointNotFoundError", "revise_data_point"]
