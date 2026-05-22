"""record_intake_and_create_case orchestration (D127, D128).

The intake-canonical orchestration behind POST ``/api/v1/cases`` and
the CLI ``portfolio create-case`` command. It records an IntakeRecord
first, then drives the Case write through the consumer-defined
``PortfolioWriter`` port with the ``intake_id`` propagated.

Dual decorators (D126): the intake permission then the portfolio
permission, so both authorisation checks fail-fast before any write
side effect. The orchestration and the use cases it composes each
carry their own decorator; the repeated check is idempotent and the
orchestration's pair is the fail-fast surface.

Transaction semantics (D128): the orchestration writes across two
bounded contexts whose adapters each open their own per-call
transaction. The IntakeRecord writes first; if the downstream Case
write fails, the IntakeRecord persists as the canonical
record-of-attempt — structurally honest for the audit-trail
integrity argument.
"""

from __future__ import annotations

from contexts.audit.domain.ports import AuditPort

from contexts.intake.application.ports.portfolio_writer import (
    CaseWriteResult,
    PortfolioWriter,
)
from contexts.intake.application.record_intake import record_intake
from contexts.intake.domain import IntakePayload, IntakeSource
from contexts.intake.ports.intake_repository import IntakeRepository
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    INTAKE_RECORD_CREATE,
    PORTFOLIO_CASE_CREATE,
    requires_authorisation,
)


@requires_authorisation(INTAKE_RECORD_CREATE)
@requires_authorisation(PORTFOLIO_CASE_CREATE)
async def record_intake_and_create_case(
    *,
    intake_repository: IntakeRepository,
    audit_port: AuditPort,
    portfolio_writer: PortfolioWriter,
    actor: ActorContext,
    payload: IntakePayload,
    title: str,
) -> CaseWriteResult:
    """Record an intake, then create a Case carrying its intake_id."""
    intake = await record_intake(
        repository=intake_repository,
        audit_port=audit_port,
        actor=actor,
        intake_source=IntakeSource.MANUAL_ENTRY,
        payload=payload,
    )
    return await portfolio_writer.create_case(
        actor=actor, title=title, intake_id=intake.id
    )


__all__ = ["record_intake_and_create_case"]
