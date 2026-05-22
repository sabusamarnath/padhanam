"""Composition wiring for the manual entry cell's PortfolioGateway (S46).

``PortfolioGatewayAdapter`` implements the messaging context's
consumer-defined ``PortfolioGateway`` port (S46 Finding D). It is the
legal cross-context seam: ``apps/`` may import
``contexts.intake.application`` and ``contexts.portfolio.application``
directly, so this adapter

- drives the three intake-canonical orchestrations
  (``record_intake_and_create_case`` and siblings) for the cell's
  writes, translating their intake-owned ``CaseWriteResult`` /
  ``DataPointWriteResult`` into the messaging-owned gateway DTOs;
- invokes the portfolio ``list_cases`` and ``get_case_detail`` read
  use cases for the cell's target resolution.

Lands in its own module rather than growing ``_messaging_wiring.py``
(298 lines — adding the gateway adapter would push it past the
300-line topology guideline) per the S44b ``_intake_wiring.py``
precedent.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable
from uuid import UUID

from apps.api._intake_wiring import (
    IntakeRepositoryAdapter,
    PortfolioWriterAdapter,
    build_intake_repository,
    build_portfolio_writer,
)
from contexts.audit.domain.ports import AuditPort
from contexts.intake.application.record_intake_and_create_case import (
    record_intake_and_create_case,
)
from contexts.intake.application.record_intake_and_create_data_point import (
    record_intake_and_create_data_point,
)
from contexts.intake.application.record_intake_and_revise_data_point import (
    record_intake_and_revise_data_point,
)
from contexts.intake.domain import ManualEntryPayload
from contexts.messaging.application.ports.portfolio_gateway import (
    CaseSummary,
    CaseWriteOutcome,
    DataPointSummary,
    DataPointWriteOutcome,
)
from contexts.portfolio.adapters.outbound.postgres.portfolio_reader import (
    PostgresPortfolioReader,
)
from contexts.portfolio.application.get_case_detail import get_case_detail
from contexts.portfolio.application.list_cases import list_cases
from contexts.tenancy.adapters.outbound.postgres.registry import (
    PostgresTenantRegistry,
)
from contexts.tenancy.application.connection_resolution import (
    TenantSessionFactoryCache,
)
from padhanam.observability.security_events import SecurityEventLogger
from padhanam.security import Principal
from shared_kernel import ActorContext, TenantContext, TenantId

_SessionFactoryForTenant = Callable[[TenantContext], Awaitable[Any]]

# A generous single-page scan for Phase 2-A target resolution — the
# operator's portfolio is small at dogfooding scale. Exhaustive
# pagination is a later refinement if a tenant outgrows it.
_RESOLUTION_PAGE_SIZE = 200


def _value_label(value: dict[str, Any]) -> str:
    """Build a human label for a DataPoint from its current value.

    The cell stores data-point content as ``{"text": ...}``; fall back
    to joining any string values so resolution still has something to
    score against if the shape differs.
    """
    text = value.get("text")
    if isinstance(text, str) and text.strip():
        return text
    return " ".join(str(v) for v in value.values() if isinstance(v, str))


class PortfolioGatewayAdapter:
    """apps/ adapter implementing the messaging PortfolioGateway port.

    Holds the intake repository and PortfolioWriter the orchestrations
    need, the audit port, and a per-tenant session factory for the
    portfolio reader the resolution reads use.
    """

    def __init__(
        self,
        *,
        intake_repository: IntakeRepositoryAdapter,
        portfolio_writer: PortfolioWriterAdapter,
        audit_port: AuditPort,
        session_factory_for_tenant: _SessionFactoryForTenant,
    ) -> None:
        self._intake_repository = intake_repository
        self._portfolio_writer = portfolio_writer
        self._audit_port = audit_port
        self._session_factory_for_tenant = session_factory_for_tenant

    async def _reader(
        self, tenant_context: TenantContext
    ) -> PostgresPortfolioReader:
        sessionmaker = await self._session_factory_for_tenant(tenant_context)

        async def _resolver(_tid: TenantId) -> object:
            return sessionmaker

        return PostgresPortfolioReader(
            per_tenant_sessionmaker_resolver=_resolver,
            bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
        )

    async def find_cases(
        self, *, actor: ActorContext
    ) -> tuple[CaseSummary, ...]:
        reader = await self._reader(actor.tenant_context)
        page = await list_cases(
            reader=reader, actor=actor, page_size=_RESOLUTION_PAGE_SIZE
        )
        return tuple(
            CaseSummary(case_id=case.id, title=case.title)
            for case in page.cases
        )

    async def find_data_points(
        self, *, actor: ActorContext
    ) -> tuple[DataPointSummary, ...]:
        reader = await self._reader(actor.tenant_context)
        page = await list_cases(
            reader=reader, actor=actor, page_size=_RESOLUTION_PAGE_SIZE
        )
        summaries: list[DataPointSummary] = []
        for case in page.cases:
            detail = await get_case_detail(
                reader=reader, actor=actor, case_id=case.id
            )
            if detail is None:
                continue
            for data_point in detail.data_points:
                summaries.append(
                    DataPointSummary(
                        data_point_id=data_point.id,
                        case_id=data_point.case_id,
                        data_point_type=data_point.data_point_type.value,
                        label=_value_label(data_point.current_value),
                    )
                )
        return tuple(summaries)

    async def create_case(
        self, *, actor: ActorContext, raw_text: str, title: str
    ) -> CaseWriteOutcome:
        result = await record_intake_and_create_case(
            intake_repository=self._intake_repository,
            audit_port=self._audit_port,
            portfolio_writer=self._portfolio_writer,
            actor=actor,
            payload=ManualEntryPayload(raw_text=raw_text),
            title=title,
        )
        return CaseWriteOutcome(
            case_id=result.case_id,
            intake_id=result.intake_id,
            title=result.title,
        )

    async def create_data_point(
        self,
        *,
        actor: ActorContext,
        raw_text: str,
        case_id: UUID,
        data_point_type: str,
        value: dict[str, Any],
    ) -> DataPointWriteOutcome:
        result = await record_intake_and_create_data_point(
            intake_repository=self._intake_repository,
            audit_port=self._audit_port,
            portfolio_writer=self._portfolio_writer,
            actor=actor,
            payload=ManualEntryPayload(raw_text=raw_text),
            case_id=case_id,
            data_point_type=data_point_type,
            value=value,
        )
        return DataPointWriteOutcome(
            data_point_id=result.data_point_id,
            case_id=result.case_id,
            intake_id=result.intake_id,
            assertion_ids=result.assertion_ids,
        )

    async def revise_data_point(
        self,
        *,
        actor: ActorContext,
        raw_text: str,
        data_point_id: UUID,
        value: dict[str, Any],
    ) -> DataPointWriteOutcome:
        result = await record_intake_and_revise_data_point(
            intake_repository=self._intake_repository,
            audit_port=self._audit_port,
            portfolio_writer=self._portfolio_writer,
            actor=actor,
            payload=ManualEntryPayload(raw_text=raw_text),
            data_point_id=data_point_id,
            value=value,
        )
        return DataPointWriteOutcome(
            data_point_id=result.data_point_id,
            case_id=result.case_id,
            intake_id=result.intake_id,
            assertion_ids=result.assertion_ids,
        )


def build_portfolio_gateway(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
    audit_port: AuditPort,
) -> PortfolioGatewayAdapter:
    """Wire the PortfolioGateway consumer-port adapter (S46, Finding D)."""

    async def _session_factory_for_tenant(
        tenant_context: TenantContext,
    ) -> Any:
        return await session_factory_cache.get(
            tenant_id=TenantId(str(tenant_context.tenant_id)),
            principal=operator_principal,
            registry=tenant_registry,
            security_events=security_events,
        )

    return PortfolioGatewayAdapter(
        intake_repository=build_intake_repository(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        ),
        portfolio_writer=build_portfolio_writer(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
            audit_port=audit_port,
        ),
        audit_port=audit_port,
        session_factory_for_tenant=_session_factory_for_tenant,
    )


__all__ = ["PortfolioGatewayAdapter", "build_portfolio_gateway"]
