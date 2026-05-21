"""revise_data_point use case (D124, D125).

Loads a DataPoint with its revision history, applies the Revisable
Protocol's ``revise`` (which appends a REVISION assertion), persists
the new assertion, and emits a ``portfolio.data_point.revise`` audit
event. Returns the revised DataPoint.
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
from shared_kernel import ActorReference, AssertionChange, TenantContext


class DataPointNotFoundError(Exception):
    """Raised when ``revise_data_point`` targets an unknown data point."""

    def __init__(self, data_point_id: UUID) -> None:
        super().__init__(f"data point {data_point_id} not found")
        self.data_point_id = data_point_id


async def revise_data_point(
    *,
    tenant_context: TenantContext,
    repository: PortfolioRepository,
    reader: PortfolioReader,
    audit_port: AuditPort,
    actor: ActorReference,
    data_point_id: UUID,
    value: dict[str, Any],
) -> DataPoint:
    """Append a revision to a DataPoint; persist and audit it."""
    existing = await reader.get_data_point(
        tenant_context=tenant_context, data_point_id=data_point_id
    )
    if existing is None:
        raise DataPointNotFoundError(data_point_id)
    revised = existing.revise(AssertionChange(value=value), actor)
    new_assertion = revised.assertions[-1]
    await repository.save_assertion(
        tenant_context=tenant_context, assertion=new_assertion
    )
    await audit_port.emit(
        draft_data_point_revise(
            tenant_context=tenant_context,
            data_point_id=data_point_id,
            new_assertion=new_assertion,
            actor=actor,
        )
    )
    return revised


__all__ = ["DataPointNotFoundError", "revise_data_point"]
