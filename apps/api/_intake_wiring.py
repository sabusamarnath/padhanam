"""Composition wiring for the intake write surface (D127, D128, S44b).

Two per-request-tenant-resolving wiring adapters plus their builders:

- ``IntakeRepositoryAdapter`` implements the intake context's
  ``IntakeRepository`` port by routing each call to a freshly-built
  ``PostgresIntakeRepository`` bound to the request's tenant.

- ``PortfolioWriterAdapter`` implements the intake context's
  consumer-defined ``PortfolioWriter`` port (D127 alternative (e)).
  It is the legal cross-context seam: ``apps/`` may import
  ``contexts.portfolio.application`` directly, so this adapter
  invokes the portfolio use cases and translates their domain
  aggregates into the intake-owned ``CaseWriteResult`` /
  ``DataPointWriteResult`` DTOs.

Lands in this module rather than ``apps/api/_agent_runtime_wiring.py``
because that file is already past its 600-line split trigger
(S44b file-topology-budget finding 5).
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable
from uuid import UUID

from contexts.audit.domain.ports import AuditPort

from contexts.intake.adapters.outbound.postgres.intake_repository import (
    PostgresIntakeRepository,
)
from contexts.intake.application.ports.portfolio_writer import (
    CaseWriteResult,
    DataPointWriteResult,
)
from contexts.intake.domain import IntakeRecord
from contexts.intake.domain.query_filters import (
    IntakeListCursor,
    IntakeListFilters,
)
from contexts.intake.ports.intake_repository import IntakeListPage
from contexts.portfolio.adapters.outbound.postgres.portfolio_reader import (
    PostgresPortfolioReader,
)
from contexts.portfolio.adapters.outbound.postgres.portfolio_repository import (
    PostgresPortfolioRepository,
)
from contexts.portfolio.application import (
    create_case,
    create_data_point,
    revise_data_point,
)
from contexts.portfolio.domain import Case, DataPoint, DataPointType
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


def _case_write_result(case: Case, intake_id: UUID) -> CaseWriteResult:
    return CaseWriteResult(
        case_id=case.id,
        tenant_id=case.tenant_id,
        jurisdiction=case.jurisdiction,
        title=case.title,
        case_type=case.case_type.value,
        status=case.status.value,
        created_at=case.created_at,
        updated_at=case.updated_at,
        intake_id=intake_id,
    )


def _data_point_write_result(
    data_point: DataPoint, intake_id: UUID
) -> DataPointWriteResult:
    return DataPointWriteResult(
        data_point_id=data_point.id,
        case_id=data_point.case_id,
        data_point_type=data_point.data_point_type.value,
        current_value=data_point.current_value,
        assertion_ids=tuple(a.id for a in data_point.assertions),
        intake_id=intake_id,
    )


class IntakeRepositoryAdapter:
    """Per-request-tenant-resolving wiring for the IntakeRepository port."""

    def __init__(
        self, *, session_factory_for_tenant: _SessionFactoryForTenant
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant

    async def _build(
        self, tenant_context: TenantContext
    ) -> PostgresIntakeRepository:
        sessionmaker = await self._session_factory_for_tenant(tenant_context)

        async def _resolver(_tid: TenantId) -> object:
            return sessionmaker

        return PostgresIntakeRepository(
            per_tenant_sessionmaker_resolver=_resolver,
            bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
        )

    async def save(
        self, *, tenant_context: TenantContext, intake: IntakeRecord
    ) -> None:
        repo = await self._build(tenant_context)
        await repo.save(tenant_context=tenant_context, intake=intake)

    async def get_by_id(
        self, *, tenant_context: TenantContext, intake_id: UUID
    ) -> IntakeRecord | None:
        repo = await self._build(tenant_context)
        return await repo.get_by_id(
            tenant_context=tenant_context, intake_id=intake_id
        )

    async def list_for_tenant(
        self,
        *,
        tenant_context: TenantContext,
        filters: IntakeListFilters | None,
        cursor: IntakeListCursor | None,
        page_size: int,
    ) -> IntakeListPage:
        repo = await self._build(tenant_context)
        return await repo.list_for_tenant(
            tenant_context=tenant_context,
            filters=filters,
            cursor=cursor,
            page_size=page_size,
        )


class PortfolioWriterAdapter:
    """apps/ adapter implementing the intake context's PortfolioWriter port.

    The legal cross-context seam (D127 alternative (e)): invokes the
    portfolio use cases and translates their domain aggregates into
    the intake-owned result DTOs.
    """

    def __init__(
        self,
        *,
        session_factory_for_tenant: _SessionFactoryForTenant,
        audit_port: AuditPort,
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant
        self._audit_port = audit_port

    async def _repo(
        self, tenant_context: TenantContext
    ) -> PostgresPortfolioRepository:
        sessionmaker = await self._session_factory_for_tenant(tenant_context)

        async def _resolver(_tid: TenantId) -> object:
            return sessionmaker

        return PostgresPortfolioRepository(
            per_tenant_sessionmaker_resolver=_resolver,
            bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
        )

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

    async def create_case(
        self, *, actor: ActorContext, title: str, intake_id: UUID
    ) -> CaseWriteResult:
        repository = await self._repo(actor.tenant_context)
        case = await create_case(
            repository=repository,
            audit_port=self._audit_port,
            actor=actor,
            title=title,
            intake_id=intake_id,
        )
        return _case_write_result(case, intake_id)

    async def create_data_point(
        self,
        *,
        actor: ActorContext,
        case_id: UUID,
        data_point_type: str,
        value: dict[str, Any],
        intake_id: UUID,
    ) -> DataPointWriteResult:
        repository = await self._repo(actor.tenant_context)
        data_point = await create_data_point(
            repository=repository,
            audit_port=self._audit_port,
            actor=actor,
            case_id=case_id,
            data_point_type=DataPointType(data_point_type),
            value=value,
            intake_id=intake_id,
        )
        return _data_point_write_result(data_point, intake_id)

    async def revise_data_point(
        self,
        *,
        actor: ActorContext,
        data_point_id: UUID,
        value: dict[str, Any],
        intake_id: UUID,
    ) -> DataPointWriteResult:
        repository = await self._repo(actor.tenant_context)
        reader = await self._reader(actor.tenant_context)
        data_point = await revise_data_point(
            repository=repository,
            reader=reader,
            audit_port=self._audit_port,
            actor=actor,
            data_point_id=data_point_id,
            value=value,
            intake_id=intake_id,
        )
        return _data_point_write_result(data_point, intake_id)


def _session_factory_for_tenant_builder(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> _SessionFactoryForTenant:
    async def _session_factory_for_tenant(
        tenant_context: TenantContext,
    ) -> Any:
        return await session_factory_cache.get(
            tenant_id=TenantId(str(tenant_context.tenant_id)),
            principal=operator_principal,
            registry=tenant_registry,
            security_events=security_events,
        )

    return _session_factory_for_tenant


def build_intake_repository(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> IntakeRepositoryAdapter:
    """Wire the intake repository for the production composition (D127)."""
    return IntakeRepositoryAdapter(
        session_factory_for_tenant=_session_factory_for_tenant_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        ),
    )


def build_portfolio_writer(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
    audit_port: AuditPort,
) -> PortfolioWriterAdapter:
    """Wire the PortfolioWriter consumer-port adapter (D127 alternative (e))."""
    return PortfolioWriterAdapter(
        session_factory_for_tenant=_session_factory_for_tenant_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        ),
        audit_port=audit_port,
    )


__all__ = [
    "IntakeRepositoryAdapter",
    "PortfolioWriterAdapter",
    "build_intake_repository",
    "build_portfolio_writer",
]
