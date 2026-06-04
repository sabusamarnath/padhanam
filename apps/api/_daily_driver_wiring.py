"""Composition wiring for the daily-driver context (D157, S58).

Three per-request-tenant-resolving wrappers live on ``app.state`` and
are dependency-injected by the daily-driver routes:

- ``CommitmentRepositoryRouter`` / ``DayRepositoryRouter`` — each call
  resolves the request's per-tenant session factory and delegates to a
  freshly-constructed bound Postgres adapter (the
  ``PortfolioReaderAdapter`` precedent: one composed instance, many
  tenants across requests).
- ``OpenCasesReaderAdapter`` — implements the daily-driver
  ``OpenCasesReader`` consumer port (the D17 cross-context seam) by
  composing the portfolio ``list_cases`` use case filtered to OPEN and
  mapping each ``Case`` onto the daily-driver-local ``OpenCase``
  projection. Mirrors the daily-briefing ``DailyBriefingReaderAdapter``
  precedent: ``apps/`` may import producer-context application modules
  directly.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Awaitable, Callable
from uuid import UUID

from contexts.daily_driver.adapters.outbound.postgres.commitment_repository import (  # noqa: E501
    PostgresCommitmentRepository,
)
from contexts.daily_driver.adapters.outbound.postgres.day_repository import (
    PostgresDayRepository,
)
from contexts.daily_driver.domain.commitment import (
    Commitment,
    CommitmentActivity,
    CommitmentCompletion,
)
from contexts.daily_driver.domain.day import DayItemState
from contexts.daily_driver.domain.today_item import ItemKind, OpenCase
from contexts.portfolio.adapters.outbound.postgres.portfolio_reader import (
    PostgresPortfolioReader,
)
from contexts.portfolio.application.list_cases import list_cases
from contexts.portfolio.domain.case import CaseStatus
from contexts.portfolio.domain.query_filters import CaseListFilters
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

_OPEN_CASE_PAGE_SIZE = 200


def _session_factory_builder(
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


def _resolver_for(sessionmaker: object) -> Callable[[TenantId], Awaitable[object]]:
    async def _resolver(_tid: TenantId) -> object:
        return sessionmaker

    return _resolver


class CommitmentRepositoryRouter:
    """Per-request-tenant-resolving ``CommitmentRepository`` (D157)."""

    def __init__(
        self, *, session_factory_for_tenant: _SessionFactoryForTenant
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant

    async def _build(
        self, tenant_context: TenantContext
    ) -> PostgresCommitmentRepository:
        sessionmaker = await self._session_factory_for_tenant(tenant_context)
        return PostgresCommitmentRepository(
            per_tenant_sessionmaker_resolver=_resolver_for(sessionmaker),
            bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
        )

    async def add_commitment(
        self, *, tenant_context: TenantContext, commitment: Commitment
    ) -> None:
        repo = await self._build(tenant_context)
        await repo.add_commitment(
            tenant_context=tenant_context, commitment=commitment
        )

    async def add_completion(
        self,
        *,
        tenant_context: TenantContext,
        completion: CommitmentCompletion,
    ) -> None:
        repo = await self._build(tenant_context)
        await repo.add_completion(
            tenant_context=tenant_context, completion=completion
        )

    async def get_commitment(
        self, *, tenant_context: TenantContext, commitment_id: UUID
    ) -> Commitment | None:
        repo = await self._build(tenant_context)
        return await repo.get_commitment(
            tenant_context=tenant_context, commitment_id=commitment_id
        )

    async def list_with_activity(
        self, *, tenant_context: TenantContext
    ) -> tuple[CommitmentActivity, ...]:
        repo = await self._build(tenant_context)
        return await repo.list_with_activity(tenant_context=tenant_context)


class DayRepositoryRouter:
    """Per-request-tenant-resolving ``DayRepository`` (D157)."""

    def __init__(
        self, *, session_factory_for_tenant: _SessionFactoryForTenant
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant

    async def _build(
        self, tenant_context: TenantContext
    ) -> PostgresDayRepository:
        sessionmaker = await self._session_factory_for_tenant(tenant_context)
        return PostgresDayRepository(
            per_tenant_sessionmaker_resolver=_resolver_for(sessionmaker),
            bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
        )

    async def get_states(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        day_date: date,
    ) -> tuple[DayItemState, ...]:
        repo = await self._build(tenant_context)
        return await repo.get_states(
            tenant_context=tenant_context,
            user_id=user_id,
            day_date=day_date,
        )

    async def set_positions(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        day_date: date,
        ordered_keys: tuple[tuple[ItemKind, UUID], ...],
    ) -> None:
        repo = await self._build(tenant_context)
        await repo.set_positions(
            tenant_context=tenant_context,
            user_id=user_id,
            day_date=day_date,
            ordered_keys=ordered_keys,
        )

    async def set_done(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        day_date: date,
        kind: ItemKind,
        item_id: UUID,
        done: bool,
    ) -> None:
        repo = await self._build(tenant_context)
        await repo.set_done(
            tenant_context=tenant_context,
            user_id=user_id,
            day_date=day_date,
            kind=kind,
            item_id=item_id,
            done=done,
        )


class OpenCasesReaderAdapter:
    """apps/ adapter implementing daily-driver's ``OpenCasesReader`` (D157, D17)."""

    def __init__(
        self, *, session_factory_for_tenant: _SessionFactoryForTenant
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant

    async def list_open_cases(
        self, *, actor: ActorContext
    ) -> tuple[OpenCase, ...]:
        sessionmaker = await self._session_factory_for_tenant(
            actor.tenant_context
        )
        reader = PostgresPortfolioReader(
            per_tenant_sessionmaker_resolver=_resolver_for(sessionmaker),
            bound_tenant_id=TenantId(str(actor.tenant_context.tenant_id)),
        )
        page = await list_cases(
            reader=reader,
            actor=actor,
            filters=CaseListFilters(statuses=(CaseStatus.OPEN,)),
            page_size=_OPEN_CASE_PAGE_SIZE,
        )
        return tuple(
            OpenCase(
                case_id=case.id,
                title=case.title,
                created_at=case.created_at,
            )
            for case in page.cases
        )


def build_commitment_repository(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> CommitmentRepositoryRouter:
    """Wire the daily-driver CommitmentRepository (D157)."""
    return CommitmentRepositoryRouter(
        session_factory_for_tenant=_session_factory_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        )
    )


def build_day_repository(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> DayRepositoryRouter:
    """Wire the daily-driver DayRepository (D157)."""
    return DayRepositoryRouter(
        session_factory_for_tenant=_session_factory_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        )
    )


def build_open_cases_reader(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> OpenCasesReaderAdapter:
    """Wire the daily-driver OpenCasesReader consumer adapter (D157, D17)."""
    return OpenCasesReaderAdapter(
        session_factory_for_tenant=_session_factory_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        )
    )


__all__ = [
    "CommitmentRepositoryRouter",
    "DayRepositoryRouter",
    "OpenCasesReaderAdapter",
    "build_commitment_repository",
    "build_day_repository",
    "build_open_cases_reader",
]
