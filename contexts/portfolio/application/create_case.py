"""create_case use case (D124, D126).

Mints a Case, persists it through the repository, and emits a
``portfolio.case.create`` audit event. The Case opens in OPEN
status by default.

S44a (D126): the use case accepts an ActorContext, applies the
``requires_authorisation`` decorator at the boundary, extracts
``actor.tenant_context`` for adapter calls, and derives an
``ActorReference`` from ``actor.actor_id`` for the audit-event
draft's persisted authoring identity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.audit.domain.ports import AuditPort

from contexts.portfolio.application.audit_events import draft_case_create
from contexts.portfolio.domain import Case, CaseStatus, CaseType
from contexts.portfolio.ports import PortfolioRepository
from shared_kernel import ActorContext, ActorReference
from shared_kernel.authorisation import (
    PORTFOLIO_CASE_CREATE,
    requires_authorisation,
)


@requires_authorisation(PORTFOLIO_CASE_CREATE)
async def create_case(
    *,
    repository: PortfolioRepository,
    audit_port: AuditPort,
    actor: ActorContext,
    title: str,
    case_type: CaseType = CaseType.PORTFOLIO_ITEM,
    status: CaseStatus = CaseStatus.OPEN,
    intake_id: UUID | None = None,
) -> Case:
    """Create and persist a Case; emit the case-create audit event.

    ``intake_id`` (D128) is populated by the intake-canonical
    orchestration; a direct call leaves the Case's ``intake_id``
    null.
    """
    tenant_context = actor.tenant_context
    authored_by = ActorReference(user_id=actor.actor_id)
    now = datetime.now(timezone.utc)
    case = Case(
        id=uuid4(),
        tenant_id=UUID(tenant_context.tenant_id),
        jurisdiction=tenant_context.jurisdiction,
        title=title,
        case_type=case_type,
        status=status,
        created_at=now,
        updated_at=now,
        intake_id=intake_id,
    )
    await repository.save_case(tenant_context=tenant_context, case=case)
    await audit_port.emit(
        draft_case_create(
            tenant_context=tenant_context, case=case, actor=authored_by
        )
    )
    return case


__all__ = ["create_case"]
