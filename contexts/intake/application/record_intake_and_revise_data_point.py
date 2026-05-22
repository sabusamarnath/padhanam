"""record_intake_and_revise_data_point orchestration (D127, D128).

The intake-canonical orchestration behind PATCH
``/api/v1/data_points/{id}`` and the CLI ``portfolio
revise-data-point`` command. It records an IntakeRecord first, then
drives the DataPoint revision through the consumer-defined
``PortfolioWriter`` port with the ``intake_id`` stamped on the
appended REVISION assertion.

Dual decorators (D126): the intake permission then the portfolio
revise permission, fail-fast before any write side effect.
Transaction semantics per D128: intake-first, two transactions; an
orphaned IntakeRecord on downstream failure is the honest
record-of-attempt.
"""

from __future__ import annotations

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
    PORTFOLIO_DATA_POINT_REVISE,
    requires_authorisation,
)
from uuid import UUID
from typing import Any


@requires_authorisation(INTAKE_RECORD_CREATE)
@requires_authorisation(PORTFOLIO_DATA_POINT_REVISE)
async def record_intake_and_revise_data_point(
    *,
    intake_repository: IntakeRepository,
    audit_port: AuditPort,
    portfolio_writer: PortfolioWriter,
    actor: ActorContext,
    payload: IntakePayload,
    data_point_id: UUID,
    value: dict[str, Any],
) -> DataPointWriteResult:
    """Record an intake, then revise a DataPoint stamping its intake_id."""
    intake = await record_intake(
        repository=intake_repository,
        audit_port=audit_port,
        actor=actor,
        intake_source=IntakeSource.MANUAL_ENTRY,
        payload=payload,
    )
    return await portfolio_writer.revise_data_point(
        actor=actor,
        data_point_id=data_point_id,
        value=value,
        intake_id=intake.id,
    )


__all__ = ["record_intake_and_revise_data_point"]
