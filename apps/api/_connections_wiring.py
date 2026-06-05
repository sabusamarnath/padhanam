"""Composition wiring for the in-product Connections page (D159, design-language §9).

The Connections page is login-aware and read-only (D148): it shows
whether the tenant's Google Calendar is connected, the read-only scope,
and the calendar-to-domain tag. This reader resolves the connection
status per request by querying the calendar context's connections table
through the tenant's session factory (the composition-root lookup the
messaging calendar runner already uses), and reads the domain-tag default
from CalendarSettings.

The OAuth connect itself happens out of band via the self-hosted Nango
connect flow (operator-gated at the dogfooding smoke, AC8); this surface
reports state and carries the read-only posture, it does not mint tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import sqlalchemy as sa

from contexts.calendar.adapters.outbound.postgres._tables import (
    connections as calendar_connections_table,
)
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

_GOOGLE_CALENDAR = "google-calendar"
_CALENDAR_SCOPE = "calendar.readonly"


@dataclass(frozen=True)
class ConnectionStatus:
    """One connectable provider's state for the Connections page."""

    provider: str
    name: str
    connected: bool
    read_only_scope: str | None
    domain_tag: str | None
    list_wired: bool


@dataclass(frozen=True)
class ConnectionsView:
    """The Connections page state: calendar live, mail/Drive connectable."""

    calendar: ConnectionStatus
    others: tuple[ConnectionStatus, ...]


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


class ConnectionsStatusReader:
    """Reads the tenant's connection status for the Connections page (D159, §9)."""

    def __init__(
        self,
        *,
        session_factory_for_tenant: _SessionFactoryForTenant,
        domain_tag: str,
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant
        self._domain_tag = domain_tag

    async def status(self, *, actor: ActorContext) -> ConnectionsView:
        sessionmaker = await self._session_factory_for_tenant(
            actor.tenant_context
        )
        connected = await self._calendar_connected(
            sessionmaker, tenant_id=str(actor.tenant_context.tenant_id)
        )
        calendar = ConnectionStatus(
            provider=_GOOGLE_CALENDAR,
            name="Google Calendar",
            connected=connected,
            read_only_scope=_CALENDAR_SCOPE,
            domain_tag=self._domain_tag if connected else self._domain_tag,
            list_wired=True,
        )
        # Mail and Drive render as connectable per §9 but are not wired into
        # the Today list this slice (D159; email-into-list is S61).
        others = (
            ConnectionStatus(
                provider="google-mail",
                name="Gmail",
                connected=False,
                read_only_scope="gmail.readonly",
                domain_tag=None,
                list_wired=False,
            ),
            ConnectionStatus(
                provider="google-drive",
                name="Google Drive",
                connected=False,
                read_only_scope="drive.readonly",
                domain_tag=None,
                list_wired=False,
            ),
        )
        return ConnectionsView(calendar=calendar, others=others)

    async def _calendar_connected(
        self, sessionmaker: Any, *, tenant_id: str
    ) -> bool:
        stmt = sa.select(calendar_connections_table.c.id).where(
            calendar_connections_table.c.tenant_id == tenant_id,
            calendar_connections_table.c.provider_config_key == _GOOGLE_CALENDAR,
        )
        async with sessionmaker() as session:
            result = await session.execute(stmt)
            return result.first() is not None


def build_connections_status_reader(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
    domain_tag: str,
) -> ConnectionsStatusReader:
    """Wire the Connections status reader (D159, design-language §9)."""
    return ConnectionsStatusReader(
        session_factory_for_tenant=_session_factory_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        ),
        domain_tag=domain_tag,
    )


__all__ = [
    "ConnectionStatus",
    "ConnectionsStatusReader",
    "ConnectionsView",
    "build_connections_status_reader",
]
