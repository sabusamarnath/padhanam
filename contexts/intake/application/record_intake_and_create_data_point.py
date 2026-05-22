"""record_intake_and_create_data_point orchestration (D127, D128).

The intake-canonical orchestration behind POST ``/api/v1/data_points``
and the CLI ``portfolio create-data-point`` command. It records an
IntakeRecord first, then drives the DataPoint creation through the
consumer-defined ``PortfolioWriter`` port with the ``intake_id``
stamped on the INITIAL assertion.

This is the third orchestration of the same intake-canonical pattern
(record intake, drive a downstream-context write, propagate
intake_id). Per D127 alternative (d) the three orchestrations stay
at ``contexts/intake/application/`` — they are one architectural
concern, not three; the ``contexts/orchestration/`` trigger is a
distinct concern, not an instance count.

Dual decorators (D126): the intake permission then the portfolio
create permission, fail-fast before any write. Transaction
semantics per D128: intake-first, two transactions.

``data_point_type`` crosses the port as a ``str`` — the intake
context does not import the portfolio ``DataPointType`` enum; the
wiring adapter converts.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from contexts.audit.domain.ports import AuditPort

from contexts.intake.application.ports.portfolio_writer import (
    DataPointWriteResult,
    PortfolioWriter,
)
from contexts.intake.application.record_intake import record_intake
from contexts.intake.domain import IntakePayload, IntakeSource
from contexts.intake.ports.intake_repository import IntakeRepository
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    INTAKE_RECORD_CREATE,
    PORTFOLIO_DATA_POINT_CREATE,
    requires_authorisation,
)


@requires_authorisation(INTAKE_RECORD_CREATE)
@requires_authorisation(PORTFOLIO_DATA_POINT_CREATE)
async def record_intake_and_create_data_point(
    *,
    intake_repository: IntakeRepository,
    audit_port: AuditPort,
    portfolio_writer: PortfolioWriter,
    actor: ActorContext,
    payload: IntakePayload,
    case_id: UUID,
    data_point_type: str,
    value: dict[str, Any],
) -> DataPointWriteResult:
    """Record an intake, then create a DataPoint stamping its intake_id."""
    intake = await record_intake(
        repository=intake_repository,
        audit_port=audit_port,
        actor=actor,
        intake_source=IntakeSource.MANUAL_ENTRY,
        payload=payload,
    )
    return await portfolio_writer.create_data_point(
        actor=actor,
        case_id=case_id,
        data_point_type=data_point_type,
        value=value,
        intake_id=intake.id,
    )


__all__ = ["record_intake_and_create_data_point"]
