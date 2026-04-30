"""Postgres audit adapter (D22, D35, D37).

Implements ``AuditPort`` against per-destination Postgres tables. Routes
events at adapter entry per D35:

  - empty-string ``tenant_id`` → control-plane ``tenant_audit`` table
    on the control-plane database.
  - non-empty ``tenant_id`` → per-tenant ``tenant_audit`` table on the
    routed tenant's data plane (resolved via the tenancy
    ``get_tenant_session_factory`` routing layer per D36).

Hash chain integrity (D22) is preserved under concurrent writers by
SELECT FOR UPDATE on the chain-tail row inside the same transaction
that performs the INSERT. The default READ COMMITTED isolation level
is sufficient: the tail row's lock blocks any other writer reading
the tail until this transaction commits, so two writers cannot read
the same tail and produce a divergent chain (D37). Cache of the last-
written hash is deferred per D37 — measurement first.

S12 widens ``AuditPort.emit`` to a coroutine; the adapter exposes ``emit``
and ``verify_chain`` as async methods directly. Sync callers (none
remain in the codebase as of S12) would dispatch via ``asyncio.run``
at the call site.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Protocol

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from contexts.audit.domain.events import (
    AuditEvent,
    ChainVerificationResult,
    GENESIS_HASH,
    compute_event_hash,
    verify_chain,
)
from shared_kernel import TenantId
from vadakkan.config import ControlPlaneSettings

_log = logging.getLogger("contexts.audit.postgres")

CONTROL_PLANE_TENANT_SENTINEL = ""

_metadata = sa.MetaData()

# Both the control-plane tenant_audit and the per-tenant tenant_audit
# share the same column shape (S11 + S12 migrations); one Table object
# is reused against both destinations because SQLAlchemy Table is a
# schema description, not an engine-bound handle.
tenant_audit = sa.Table(
    "tenant_audit",
    _metadata,
    sa.Column(
        "id",
        pg.UUID(as_uuid=False),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("actor", sa.Text, nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("timestamp", sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column("action_verb", sa.Text, nullable=False),
    sa.Column("resource_type", sa.Text, nullable=False),
    sa.Column("resource_id", sa.Text, nullable=False),
    sa.Column("before_state", pg.JSONB, nullable=False),
    sa.Column("after_state", pg.JSONB, nullable=False),
    sa.Column("correlation_id", sa.Text, nullable=False),
    sa.Column("previous_event_hash", sa.Text, nullable=False),
    sa.Column("this_event_hash", sa.Text, nullable=False),
)


class _SessionFactoryResolver(Protocol):
    """Resolver shape: given a non-empty TenantId, return the per-tenant
    ``async_sessionmaker``. Implemented in production by the tenancy
    routing layer (`contexts.tenancy.api.get_tenant_session_factory`)
    bound to its operator-context principal and cache. The Protocol
    keeps the audit context independent of tenancy internals (D17)."""

    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


def _control_plane_url(settings: ControlPlaneSettings) -> str:
    return (
        f"postgresql+asyncpg://{settings.user}:{settings.password}"
        f"@{settings.host}:{settings.port}/{settings.db}"
    )


class PostgresAuditAdapter:
    """Postgres-backed AuditPort with hash-chain concurrency control.

    Holds the control-plane engine + sessionmaker as instance state and
    a callback that resolves per-tenant sessionmakers on demand via the
    tenancy routing layer. No tenant credentials, plaintext or
    otherwise, are kept on the instance — the resolver is opaque to
    this adapter, which receives only ``async_sessionmaker`` opaque
    handles.
    """

    def __init__(
        self,
        *,
        control_plane_engine: AsyncEngine,
        per_tenant_sessionmaker_resolver: _SessionFactoryResolver,
    ) -> None:
        self._control_plane_engine = control_plane_engine
        self._control_plane_sessionmaker = async_sessionmaker(
            control_plane_engine, expire_on_commit=False
        )
        self._resolve_per_tenant = per_tenant_sessionmaker_resolver

    @classmethod
    def from_settings(
        cls,
        *,
        control_plane_settings: ControlPlaneSettings,
        per_tenant_sessionmaker_resolver: _SessionFactoryResolver,
    ) -> "PostgresAuditAdapter":
        engine = create_async_engine(
            _control_plane_url(control_plane_settings),
            pool_pre_ping=True,
        )
        return cls(
            control_plane_engine=engine,
            per_tenant_sessionmaker_resolver=per_tenant_sessionmaker_resolver,
        )

    async def dispose(self) -> None:
        await self._control_plane_engine.dispose()

    # ------------------------------------------------------------------
    # AuditPort implementation
    # ------------------------------------------------------------------

    async def emit(self, event: AuditEvent) -> None:
        """Write the event to its routed destination, chained against
        the destination's tail.

        The caller's ``previous_event_hash`` and ``this_event_hash`` are
        treated as draft: the adapter is the chain authority and
        recomputes both inside the SELECT-FOR-UPDATE transaction so
        concurrent writers cannot produce a divergent chain (D37).
        Callers compose ``AuditEvent`` for content; the chain hashes
        are an adapter-side derivation.
        """
        sessionmaker = await self._resolve_sessionmaker(event.tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                # SELECT FOR UPDATE on the chain-tail row inside this
                # transaction closes the SELECT-then-INSERT race (D37).
                # If no rows exist, the tail-prev is the genesis sentinel.
                tail_stmt = (
                    sa.select(tenant_audit.c.this_event_hash)
                    .order_by(tenant_audit.c.timestamp.desc(), tenant_audit.c.id.desc())
                    .limit(1)
                    .with_for_update()
                )
                result = await session.execute(tail_stmt)
                tail_hash = result.scalar_one_or_none()
                previous = tail_hash if tail_hash is not None else GENESIS_HASH
                this_hash = compute_event_hash(
                    actor=event.actor,
                    tenant_id=event.tenant_id,
                    jurisdiction=event.jurisdiction,
                    timestamp=event.timestamp,
                    action_verb=event.action_verb,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    before_state=event.before_state,
                    after_state=event.after_state,
                    correlation_id=event.correlation_id,
                    previous_event_hash=previous,
                )
                await session.execute(
                    sa.insert(tenant_audit).values(
                        tenant_id=event.tenant_id,
                        actor=event.actor,
                        jurisdiction=event.jurisdiction,
                        # asyncpg requires datetime for timestamptz; the
                        # domain field is the ISO string used in the
                        # hash payload. Parse back at the adapter
                        # boundary; the round-trip is lossless because
                        # `datetime.now(timezone.utc).isoformat()` is
                        # the source.
                        timestamp=datetime.fromisoformat(event.timestamp),
                        action_verb=event.action_verb,
                        resource_type=event.resource_type,
                        resource_id=event.resource_id,
                        before_state=event.before_state,
                        after_state=event.after_state,
                        correlation_id=event.correlation_id,
                        previous_event_hash=previous,
                        this_event_hash=this_hash,
                    )
                )

    async def verify_chain(
        self, tenant_id: TenantId
    ) -> ChainVerificationResult:
        events = await self._read_chain(tenant_id)
        return verify_chain(events)

    async def _read_chain(self, tenant_id: TenantId) -> list[AuditEvent]:
        sessionmaker = await self._resolve_sessionmaker(str(tenant_id))
        async with sessionmaker() as session:
            result = await session.execute(
                sa.select(tenant_audit).order_by(
                    tenant_audit.c.timestamp.asc(), tenant_audit.c.id.asc()
                )
            )
            rows = result.mappings().all()
        return [
            AuditEvent(
                actor=r["actor"],
                tenant_id=r["tenant_id"],
                jurisdiction=r["jurisdiction"],
                action_verb=r["action_verb"],
                resource_type=r["resource_type"],
                resource_id=r["resource_id"],
                before_state=r["before_state"],
                after_state=r["after_state"],
                correlation_id=r["correlation_id"],
                previous_event_hash=r["previous_event_hash"],
                this_event_hash=r["this_event_hash"],
                timestamp=r["timestamp"].isoformat()
                if hasattr(r["timestamp"], "isoformat")
                else str(r["timestamp"]),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _resolve_sessionmaker(
        self, tenant_id: str
    ) -> async_sessionmaker[AsyncSession]:
        if tenant_id == CONTROL_PLANE_TENANT_SENTINEL:
            return self._control_plane_sessionmaker
        return await self._resolve_per_tenant(TenantId(tenant_id))
