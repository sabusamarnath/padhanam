"""create_data_point use case (D124, D126).

Mints a DataPoint together with its INITIAL Assertion, persists both
atomically through the repository, and emits a
``portfolio.data_point.create`` audit event. The parent Case is
referenced by ``case_id``; the per-tenant FK from ``data_points`` to
``cases`` rejects an orphan or cross-tenant ``case_id`` at the data
layer.

S44a (D126): the use case accepts an ActorContext, applies the
``requires_authorisation`` decorator, extracts ``actor.tenant_context``
for adapter calls, and derives an ``ActorReference`` from
``actor.actor_id`` for the persisted ``authored_by`` identity on the
DataPoint and its INITIAL Assertion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from contexts.audit.domain.ports import AuditPort

from contexts.portfolio.application.audit_events import (
    draft_data_point_create,
)
from contexts.portfolio.domain import (
    Assertion,
    AssertionType,
    DataPoint,
    DataPointType,
)
from contexts.portfolio.ports import PortfolioRepository
from shared_kernel import ActorContext, ActorReference
from shared_kernel.authorisation import (
    PORTFOLIO_DATA_POINT_CREATE,
    requires_authorisation,
)


@requires_authorisation(PORTFOLIO_DATA_POINT_CREATE)
async def create_data_point(
    *,
    repository: PortfolioRepository,
    audit_port: AuditPort,
    actor: ActorContext,
    case_id: UUID,
    data_point_type: DataPointType,
    value: dict[str, Any],
) -> DataPoint:
    """Create a DataPoint with its INITIAL assertion; persist and audit."""
    tenant_context = actor.tenant_context
    authored_by = ActorReference(user_id=actor.actor_id)
    now = datetime.now(timezone.utc)
    tenant_uuid = UUID(tenant_context.tenant_id)
    data_point_id = uuid4()
    initial = Assertion(
        id=uuid4(),
        data_point_id=data_point_id,
        tenant_id=tenant_uuid,
        jurisdiction=tenant_context.jurisdiction,
        assertion_type=AssertionType.INITIAL,
        revises_assertion_id=None,
        value=value,
        authored_by=authored_by,
        created_at=now,
    )
    data_point = DataPoint(
        id=data_point_id,
        case_id=case_id,
        tenant_id=tenant_uuid,
        jurisdiction=tenant_context.jurisdiction,
        data_point_type=data_point_type,
        value=value,
        authored_by=authored_by,
        created_at=now,
        assertions=(initial,),
    )
    await repository.save_data_point(
        tenant_context=tenant_context, data_point=data_point
    )
    await audit_port.emit(
        draft_data_point_create(
            tenant_context=tenant_context,
            data_point=data_point,
            actor=authored_by,
        )
    )
    return data_point


__all__ = ["create_data_point"]
