"""create_case use case (D124).

Mints a Case, persists it through the repository, and emits a
``portfolio.case.create`` audit event. The Case opens in OPEN
status by default.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.audit.domain.ports import AuditPort

from contexts.portfolio.application.audit_events import draft_case_create
from contexts.portfolio.domain import Case, CaseStatus, CaseType
from contexts.portfolio.ports import PortfolioRepository
from shared_kernel import ActorReference, TenantContext


async def create_case(
    *,
    tenant_context: TenantContext,
    repository: PortfolioRepository,
    audit_port: AuditPort,
    actor: ActorReference,
    title: str,
    case_type: CaseType = CaseType.PORTFOLIO_ITEM,
    status: CaseStatus = CaseStatus.OPEN,
) -> Case:
    """Create and persist a Case; emit the case-create audit event."""
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
    )
    await repository.save_case(tenant_context=tenant_context, case=case)
    await audit_port.emit(
        draft_case_create(
            tenant_context=tenant_context, case=case, actor=actor
        )
    )
    return case


__all__ = ["create_case"]
