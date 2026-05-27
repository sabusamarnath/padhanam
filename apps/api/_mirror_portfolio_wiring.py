"""Composition wiring for the mirror-conversation MirrorPortfolioReader (S52).

The legal cross-context seam (D17): ``apps/`` may import
``contexts.portfolio.application`` directly, so this adapter
implements mirror-conversation's ``MirrorPortfolioReader`` consumer
port by composing the portfolio read use cases (``list_cases``,
``get_case_detail``) plus the portfolio reader (for direct data-point
lookup).

Lands in its own module mirroring the
``apps/api/_portfolio_gateway_wiring.py`` precedent (S46): a per-
context wiring file keeps each cross-context seam grep-able. The
shared portfolio reader builder is reused from the existing wiring
plumbing.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable
from uuid import UUID

from contexts.mirror_conversation.application.ports.mirror_portfolio_reader import (  # noqa: E501
    MirrorCaseDetail,
    MirrorCaseSummary,
    MirrorDataPoint,
    MirrorDataPointSummary,
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

# Mirror-conversation runs against the operator's portfolio at
# dogfooding scale (single-digit cases per tenant at Phase 2-A); a
# generous single-page scan covers the listing+resolution flows
# without paginating. Phase 2-B+ may swap to true pagination when
# tenant portfolios outgrow the single page.
_LIST_PAGE_SIZE = 200


def _value_label(value: dict[str, Any]) -> str:
    """Build a human label for a DataPoint from its current value."""
    text = value.get("text")
    if isinstance(text, str) and text.strip():
        return text
    return " ".join(str(v) for v in value.values() if isinstance(v, str))


class MirrorPortfolioReaderAdapter:
    """apps/ adapter implementing the mirror-conversation MirrorPortfolioReader."""

    def __init__(
        self,
        *,
        session_factory_for_tenant: _SessionFactoryForTenant,
    ) -> None:
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

    async def list_cases(
        self, *, actor: ActorContext, limit: int = 50
    ) -> tuple[MirrorCaseSummary, ...]:
        reader = await self._reader(actor.tenant_context)
        page = await list_cases(
            reader=reader, actor=actor, page_size=limit
        )
        return tuple(await self._enrich_summaries(reader, actor, page.cases))

    async def find_cases(
        self, *, actor: ActorContext
    ) -> tuple[MirrorCaseSummary, ...]:
        reader = await self._reader(actor.tenant_context)
        page = await list_cases(
            reader=reader, actor=actor, page_size=_LIST_PAGE_SIZE
        )
        return tuple(await self._enrich_summaries(reader, actor, page.cases))

    async def get_case_detail(
        self, *, actor: ActorContext, case_id: UUID
    ) -> MirrorCaseDetail | None:
        reader = await self._reader(actor.tenant_context)
        detail = await get_case_detail(
            reader=reader, actor=actor, case_id=case_id
        )
        if detail is None:
            return None
        if detail.data_points:
            last_activity = max(dp.created_at for dp in detail.data_points)
            dp_count = len(detail.data_points)
        else:
            last_activity = detail.case.created_at
            dp_count = 0
        summary = MirrorCaseSummary(
            case_id=detail.case.id,
            title=detail.case.title,
            case_status=detail.case.status.value,
            created_at=detail.case.created_at,
            last_activity_at=last_activity,
            data_point_count=dp_count,
        )
        data_points = tuple(
            MirrorDataPointSummary(
                data_point_id=dp.id,
                case_id=dp.case_id,
                data_point_type=dp.data_point_type.value,
                label=_value_label(dp.current_value),
                created_at=dp.created_at,
            )
            for dp in detail.data_points
        )
        return MirrorCaseDetail(case=summary, data_points=data_points)

    async def get_data_point(
        self, *, actor: ActorContext, data_point_id: UUID
    ) -> MirrorDataPoint | None:
        reader = await self._reader(actor.tenant_context)
        # The portfolio reader's get_data_point returns the DataPoint
        # with its full revision history per D125's Revisable Protocol.
        # We translate to the mirror-conversation DTO (a revision_count
        # summary keeps the cell's render concerns small; full
        # revision-history rendering activates if a future surface
        # demands it).
        data_point = await reader.get_data_point(
            tenant_context=actor.tenant_context,
            data_point_id=data_point_id,
        )
        if data_point is None:
            return None
        return MirrorDataPoint(
            data_point_id=data_point.id,
            case_id=data_point.case_id,
            data_point_type=data_point.data_point_type.value,
            current_value=data_point.current_value,
            created_at=data_point.created_at,
            revision_count=len(data_point.assertions),
        )

    async def _enrich_summaries(
        self,
        reader: PostgresPortfolioReader,
        actor: ActorContext,
        cases,
    ) -> list[MirrorCaseSummary]:
        summaries: list[MirrorCaseSummary] = []
        for case in cases:
            detail = await get_case_detail(
                reader=reader, actor=actor, case_id=case.id
            )
            if detail is None or not detail.data_points:
                data_point_count = 0
                last_activity_at = case.created_at
            else:
                data_point_count = len(detail.data_points)
                last_activity_at = max(
                    dp.created_at for dp in detail.data_points
                )
            summaries.append(
                MirrorCaseSummary(
                    case_id=case.id,
                    title=case.title,
                    case_status=case.status.value,
                    created_at=case.created_at,
                    last_activity_at=last_activity_at,
                    data_point_count=data_point_count,
                )
            )
        return summaries


def build_mirror_portfolio_reader(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> MirrorPortfolioReaderAdapter:
    """Wire the mirror-conversation MirrorPortfolioReader adapter."""

    async def _session_factory_for_tenant(
        tenant_context: TenantContext,
    ) -> Any:
        return await session_factory_cache.get(
            tenant_id=TenantId(str(tenant_context.tenant_id)),
            principal=operator_principal,
            registry=tenant_registry,
            security_events=security_events,
        )

    return MirrorPortfolioReaderAdapter(
        session_factory_for_tenant=_session_factory_for_tenant,
    )


__all__ = [
    "MirrorPortfolioReaderAdapter",
    "build_mirror_portfolio_reader",
]
