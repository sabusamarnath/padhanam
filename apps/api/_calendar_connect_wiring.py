"""Live calendar connect composition (D160, S60b).

The S60 Connect button was display-only. S60b wires it through a
``CalendarConnectInitiator`` port: ``initiate`` returns a connect session
the page opens (the Nango connect flow), and a callback hands the issued
provider connection reference back so a per-tenant ``Connection`` is
stored (reusing ``save_connection``) and the first ``sync_calendar`` pull
runs so live events reach the Today list.

The Nango initiator is **operator-gated** (D160): the Nango connect-session
API is a vendor contract the build environment cannot reach, and the
S55a-fix lesson is that such contracts must be reconciled against the live
service, not asserted from memory. So ``NangoCalendarConnectInitiator``
calls an injected session creator the operator wires at deploy and raises
a clear ``ConnectError`` until then. The **callback writer**
(``ConnectionStore``) is fully testable: it composes the existing
bound-tenant ``PostgresConnectionRepository.save_connection`` and an
injectable first-sync trigger (the real ``build_calendar_refresh_adapter``
by default; a stub in tests), so per-tenant isolation (D12/D24) holds on
the stored connection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Protocol
from uuid import UUID, uuid4

from contexts.calendar.domain.connection import Connection
from contexts.tenancy.adapters.outbound.postgres.registry import (
    PostgresTenantRegistry,
)
from contexts.tenancy.application.connection_resolution import (
    TenantSessionFactoryCache,
)
from padhanam.observability.security_events import SecurityEventLogger
from padhanam.security import Principal
from shared_kernel import ActorContext, TenantContext, TenantId

_GOOGLE_CALENDAR = "google-calendar"
_PROVIDER = "google_calendar"

_SessionFactoryForTenant = Callable[[TenantContext], Awaitable[Any]]
# (tenant_id, connection_id, tenant_context) -> None ; the first pull after connect.
FirstSync = Callable[[str, UUID, TenantContext], Awaitable[None]]


class ConnectError(Exception):
    """Raised when a connect session cannot be created (→ 503/operator-gated)."""


@dataclass(frozen=True)
class ConnectSession:
    """A connect session the page opens to run the provider OAuth flow."""

    provider_config_key: str
    connect_url: str | None = None
    session_token: str | None = None


@dataclass(frozen=True)
class StoredConnection:
    """The result of the connect callback: the stored connection + first-sync state."""

    connection_id: UUID
    synced: bool
    sync_error: str | None = None


class CalendarConnectInitiator(Protocol):
    """Creates a provider connect session for the actor's tenant."""

    async def create_session(self, *, actor: ActorContext) -> ConnectSession:
        """Return a connect session, or raise ``ConnectError``."""
        ...


# An operator-provided creator: given the tenant id, return a ConnectSession
# from the live Nango connect-session API. The operator wires this at deploy
# and reconciles the Nango contract at the live smoke (S55a-fix discipline).
NangoSessionCreator = Callable[[str], Awaitable[ConnectSession]]


class NangoCalendarConnectInitiator:
    """Nango connect-session initiator — operator-gated (D160).

    With no session creator wired, ``create_session`` raises a descriptive
    ``ConnectError`` rather than asserting Nango's connect-session API from
    memory. The seam (the route, the page, the callback) is real and tested;
    the vendor call is operator-provided.
    """

    def __init__(self, *, session_creator: NangoSessionCreator | None = None) -> None:
        self._create = session_creator

    async def create_session(self, *, actor: ActorContext) -> ConnectSession:
        if self._create is None:
            raise ConnectError(
                "calendar connect is operator-gated: wire the Nango "
                "connect-session creator at deploy and reconcile its "
                "contract at the live smoke (D160). Until then connect via "
                "the Nango self-hosted runbook, then POST the connection "
                "reference to the callback."
            )
        return await self._create(str(actor.tenant_context.tenant_id))


def _resolver_for(sessionmaker: object) -> Callable[[TenantId], Awaitable[object]]:
    async def _resolver(_tid: TenantId) -> object:
        return sessionmaker

    return _resolver


class ConnectionStore:
    """Stores a per-tenant calendar connection and triggers the first pull (D160).

    The connect callback hands back the provider connection reference (the
    Nango connection id). This writes the bound-tenant ``Connection`` via
    ``save_connection`` (so isolation holds — the row binds to the actor's
    tenant) and runs the first ``sync_calendar`` pull through the injected
    trigger so live events reach the Today list. The pull is operator-gated
    (network/Nango); its failure does not lose the stored connection.
    """

    def __init__(
        self,
        *,
        session_factory_for_tenant: _SessionFactoryForTenant,
        first_sync: FirstSync | None,
    ) -> None:
        self._sf = session_factory_for_tenant
        self._first_sync = first_sync

    async def store_connection(
        self, *, actor: ActorContext, provider_connection_ref: str
    ) -> StoredConnection:
        from contexts.calendar.adapters.outbound.postgres.connection_repository import (  # noqa: E501
            PostgresConnectionRepository,
        )

        if not provider_connection_ref or not provider_connection_ref.strip():
            raise ConnectError("missing provider connection reference")

        sessionmaker = await self._sf(actor.tenant_context)
        bound = TenantId(str(actor.tenant_context.tenant_id))
        repo = PostgresConnectionRepository(
            per_tenant_sessionmaker_resolver=_resolver_for(sessionmaker),
            bound_tenant_id=bound,
        )
        now = datetime.now(timezone.utc)
        connection = Connection(
            id=uuid4(),
            tenant_id=UUID(str(actor.tenant_context.tenant_id)),
            jurisdiction=actor.tenant_context.jurisdiction,
            provider=_PROVIDER,
            provider_config_key=_GOOGLE_CALENDAR,
            provider_connection_ref=provider_connection_ref.strip(),
            created_at=now,
            updated_at=now,
        )
        # Use the canonical persisted id, not connection.id: on a re-connect
        # the upsert keeps the existing row's id, so first-sync must reference
        # the stored row (else sync_calendar's get-by-id misses and raises
        # NoSuchConnectionError on the transient id).
        connection_id = await repo.save_connection(
            tenant_context=actor.tenant_context, connection=connection
        )

        if self._first_sync is None:
            return StoredConnection(connection_id=connection_id, synced=False)
        try:
            await self._first_sync(
                str(actor.tenant_context.tenant_id),
                connection_id,
                actor.tenant_context,
            )
        except (ConnectError, OSError, RuntimeError, ValueError) as exc:
            # The live pull is operator-gated; the connection is stored
            # regardless, and the next calendar turn / a manual sync pulls.
            return StoredConnection(
                connection_id=connection_id, synced=False, sync_error=str(exc)
            )
        return StoredConnection(connection_id=connection_id, synced=True)


async def _default_first_sync(
    tenant_id: str, connection_id: UUID, tenant_context: TenantContext
) -> None:
    """The real first-pull: refresh through the wired Nango refresh adapter."""
    from apps.cli._calendar import build_calendar_refresh_adapter

    adapter = build_calendar_refresh_adapter(
        tenant_id=tenant_id, connection_id=connection_id
    )
    await adapter.refresh(tenant_context=tenant_context)


def build_calendar_connect_initiator() -> CalendarConnectInitiator:
    """Wire the calendar connect initiator (Nango adapter, operator-gated)."""
    return NangoCalendarConnectInitiator()


def _session_factory_builder(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> _SessionFactoryForTenant:
    async def _session_factory_for_tenant(tenant_context: TenantContext) -> Any:
        return await session_factory_cache.get(
            tenant_id=TenantId(str(tenant_context.tenant_id)),
            principal=operator_principal,
            registry=tenant_registry,
            security_events=security_events,
        )

    return _session_factory_for_tenant


def build_connection_store(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> ConnectionStore:
    """Wire the connect-callback connection store with the real first-sync."""
    return ConnectionStore(
        session_factory_for_tenant=_session_factory_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        ),
        first_sync=_default_first_sync,
    )


__all__ = [
    "CalendarConnectInitiator",
    "ConnectError",
    "ConnectSession",
    "ConnectionStore",
    "NangoCalendarConnectInitiator",
    "NangoSessionCreator",
    "StoredConnection",
    "build_calendar_connect_initiator",
    "build_connection_store",
]
