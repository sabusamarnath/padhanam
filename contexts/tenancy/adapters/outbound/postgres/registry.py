"""Tenant registry Postgres adapter (D34).

The adapter implements TenantRegistryPort against the control-plane
Postgres instance (D33). Envelope encryption (D21) is integrated on
the credential write path; reads return EncryptedCredentials only and
do not decrypt. The dedicated reveal_connection_config method is the
operator-context-only decryption path consumed by the S11 connection-
resolution layer.

Three S10 invariants live in the structural shape of this module:

  1. **No plaintext field is ever assigned to instance state.** The
     adapter holds an engine and a session factory; the
     ``register_tenant`` and ``reveal_connection_config`` flows take
     plaintext as function-local arguments and let it go out of scope
     at function return. The AST enforcement test in
     ``tests/_enforcement/test_no_plaintext_in_state.py`` walks this
     module and fails on any class attribute typed as
     ``TenantConnectionConfig``.

  2. **AAD binds tenant_id and the fixed purpose string.** Every
     encrypt and decrypt call passes the same context dict
     ``{"tenant_id": ..., "purpose": "tenant.credentials.v1"}``.
     Cryptography's AESGCM raises InvalidTag if the AAD does not match
     at decrypt time, which prevents replay across tenants even if a
     wrapped DEK is moved row-to-row.

  3. **No credential field flows through logging.** Audit events carry
     the encrypted form by way of resource_ref summarising the row;
     security events carry only the action verb and tenant id; no
     bytes from the EncryptedField wire shape and no plaintext field
     value ever appears in a log call.

SQLAlchemy usage is Core-shaped (Table + select/insert/update via
AsyncConnection.execute) per D34; the row-to-domain conversion is
manual because Tenant is a frozen dataclass and ORM mapping mutates
instances on load.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from contexts.audit.domain.events import AuditEvent, GENESIS_HASH, compute_event_hash
from contexts.audit.domain.ports import AuditPort
from contexts.tenancy.domain.encrypted_credentials import EncryptedCredentials
from contexts.tenancy.domain.tenant import Tenant, TenantStatus
from contexts.tenancy.domain.tenant_connection_config import TenantConnectionConfig
from contexts.tenancy.domain.tenant_id import TenantId
from shared_kernel import Jurisdiction
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
)
from padhanam.security import crypto

CREDENTIAL_PURPOSE = "tenant.credentials.v1"
CONTROL_PLANE_TENANT_SENTINEL = ""

_metadata = sa.MetaData()

tenant_registry = sa.Table(
    "tenant_registry",
    _metadata,
    sa.Column("tenant_id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("display_name", sa.Text, nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column("wrapped_dek", sa.LargeBinary, nullable=False),
    sa.Column("dek_wrap_nonce", sa.LargeBinary, nullable=False),
    sa.Column("ciphertext", sa.LargeBinary, nullable=False),
    sa.Column("nonce", sa.LargeBinary, nullable=False),
    sa.Column("key_version", sa.Integer, nullable=False),
    sa.Column("aad", sa.LargeBinary, nullable=False),
)


def _aad_context(tenant_id: TenantId) -> dict[str, str]:
    """The AAD context that binds ciphertext to a tenant + purpose."""
    return {"tenant_id": str(tenant_id), "purpose": CREDENTIAL_PURPOSE}


def _serialize_plaintext(plaintext: TenantConnectionConfig) -> bytes:
    """Stable JSON encoding of plaintext credentials."""
    payload = {
        "host": plaintext.host,
        "port": plaintext.port,
        "username": plaintext.username,
        "password": plaintext.password,
        "database": plaintext.database,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _deserialize_plaintext(raw: bytes) -> TenantConnectionConfig:
    payload = json.loads(raw.decode())
    return TenantConnectionConfig(
        host=payload["host"],
        port=payload["port"],
        username=payload["username"],
        password=payload["password"],
        database=payload["database"],
    )


def _async_url(settings: ControlPlaneSettings) -> str:
    return (
        f"postgresql+asyncpg://{settings.user}:{settings.password}"
        f"@{settings.host}:{settings.port}/{settings.db}"
    )


class PostgresTenantRegistry:
    """Adapter implementation of TenantRegistryPort.

    Holds the async engine and session factory only; no plaintext
    credential reference is ever assigned to ``self``. The AST
    enforcement test inspects this class for that invariant.
    """

    def __init__(
        self,
        *,
        engine: AsyncEngine,
        audit: AuditPort,
        security_events: SecurityEventLogger,
    ) -> None:
        self._engine = engine
        self._sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        self._audit = audit
        self._security_events = security_events

    @classmethod
    def from_settings(
        cls,
        *,
        settings: ControlPlaneSettings,
        audit: AuditPort,
        security_events: SecurityEventLogger,
    ) -> "PostgresTenantRegistry":
        engine = create_async_engine(_async_url(settings), pool_pre_ping=True)
        return cls(engine=engine, audit=audit, security_events=security_events)

    async def dispose(self) -> None:
        await self._engine.dispose()

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def register_tenant(
        self,
        tenant_id: TenantId,
        jurisdiction: Jurisdiction,
        display_name: str,
        connection_config: TenantConnectionConfig,
    ) -> Tenant:
        # Encrypt before any I/O. The plaintext bytes go out of scope at
        # function return; they are never assigned to ``self``.
        plaintext_bytes = _serialize_plaintext(connection_config)
        encrypted = crypto.encrypt_field(plaintext_bytes, _aad_context(tenant_id))
        # AAD bytes that the domain object carries for cross-tenant-
        # replay tests; they are recomputable from tenant_id+purpose,
        # but persisting them keeps the EncryptedCredentials value
        # object self-contained.
        aad_bytes = crypto._serialize_aad(_aad_context(tenant_id))

        created_at = datetime.now(timezone.utc)
        async with self._sessionmaker() as session:
            await session.execute(
                sa.insert(tenant_registry).values(
                    tenant_id=str(tenant_id),
                    display_name=display_name,
                    jurisdiction=str(jurisdiction),
                    status=TenantStatus.ACTIVE.value,
                    created_at=created_at,
                    wrapped_dek=encrypted.wrapped_dek,
                    dek_wrap_nonce=encrypted.dek_wrap_nonce,
                    ciphertext=encrypted.ciphertext,
                    nonce=encrypted.nonce,
                    key_version=encrypted.key_version,
                    aad=aad_bytes,
                )
            )
            await session.commit()

        tenant = Tenant(
            id=tenant_id,
            jurisdiction=jurisdiction,
            display_name=display_name,
            credentials=EncryptedCredentials(
                wrapped_dek=encrypted.wrapped_dek,
                ciphertext=encrypted.ciphertext,
                aad=aad_bytes,
            ),
            status=TenantStatus.ACTIVE,
            created_at=created_at,
        )
        await self._emit_audit(
            actor="system:control_plane",
            action_verb="tenant.register",
            resource_id=str(tenant_id),
            before={},
            after={
                "tenant_id": str(tenant_id),
                "jurisdiction": str(jurisdiction),
                "display_name": display_name,
                "status": TenantStatus.ACTIVE.value,
            },
        )
        self._security_events.emit(
            SecurityEvent(
                category=SecurityEventCategory.PRIVILEGED_ACTION,
                principal_ref="system:control_plane",
                tenant_id=None,
                action="tenant.register",
                resource_ref=f"tenant:{tenant_id}",
                outcome="allow",
            )
        )
        return tenant

    async def get_tenant(self, tenant_id: TenantId) -> Tenant | None:
        async with self._sessionmaker() as session:
            result = await session.execute(
                sa.select(tenant_registry).where(
                    tenant_registry.c.tenant_id == str(tenant_id)
                )
            )
            row = result.mappings().first()
        if row is None:
            return None
        return _row_to_tenant(row)

    async def list_tenants(
        self, jurisdiction: Jurisdiction | None = None
    ) -> list[Tenant]:
        stmt = sa.select(tenant_registry)
        if jurisdiction is not None:
            stmt = stmt.where(tenant_registry.c.jurisdiction == str(jurisdiction))
        async with self._sessionmaker() as session:
            result = await session.execute(stmt)
            rows = result.mappings().all()
        return [_row_to_tenant(r) for r in rows]

    async def update_tenant_status(
        self, tenant_id: TenantId, status: TenantStatus
    ) -> Tenant:
        async with self._sessionmaker() as session:
            existing = await session.execute(
                sa.select(tenant_registry).where(
                    tenant_registry.c.tenant_id == str(tenant_id)
                )
            )
            before_row = existing.mappings().first()
            if before_row is None:
                raise LookupError(f"tenant {tenant_id} not found")
            await session.execute(
                sa.update(tenant_registry)
                .where(tenant_registry.c.tenant_id == str(tenant_id))
                .values(status=status.value)
            )
            await session.commit()

            after = await session.execute(
                sa.select(tenant_registry).where(
                    tenant_registry.c.tenant_id == str(tenant_id)
                )
            )
            after_row = after.mappings().first()

        await self._emit_audit(
            actor="system:control_plane",
            action_verb="tenant.update_status",
            resource_id=str(tenant_id),
            before={"status": before_row["status"]},
            after={"status": status.value},
        )
        return _row_to_tenant(after_row)

    # ------------------------------------------------------------------
    # Operator-context-only decryption path (D34).
    # ------------------------------------------------------------------

    async def reveal_connection_config(
        self, tenant_id: TenantId
    ) -> TenantConnectionConfig:
        """Return plaintext credentials. Operator-context only.

        Policy enforcement lives in the use case at the application
        layer (D34); the adapter's responsibility is the structural
        decryption path. AAD is recomputed from the row's tenant_id
        rather than read from the ``aad`` column so the binding holds
        even if the stored AAD is tampered with.
        """
        async with self._sessionmaker() as session:
            result = await session.execute(
                sa.select(tenant_registry).where(
                    tenant_registry.c.tenant_id == str(tenant_id)
                )
            )
            row = result.mappings().first()
        if row is None:
            raise LookupError(f"tenant {tenant_id} not found")

        wire = crypto.EncryptedField(
            wrapped_dek=bytes(row["wrapped_dek"]),
            dek_wrap_nonce=bytes(row["dek_wrap_nonce"]),
            ciphertext=bytes(row["ciphertext"]),
            nonce=bytes(row["nonce"]),
            key_version=int(row["key_version"]),
        )
        plaintext_bytes = crypto.decrypt_field(wire, _aad_context(tenant_id))
        return _deserialize_plaintext(plaintext_bytes)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _emit_audit(
        self,
        *,
        actor: str,
        action_verb: str,
        resource_id: str,
        before: dict,
        after: dict,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        # tenant_id sentinel for control-plane scope (D34). The S12
        # audit adapter routes events with this sentinel to the
        # control-plane audit table; per-tenant audit chains use the
        # tenant's UUID.
        tenant_id = CONTROL_PLANE_TENANT_SENTINEL
        # Genesis-prev for now; S12's real adapter walks the chain.
        previous = GENESIS_HASH
        this_hash = compute_event_hash(
            actor=actor,
            tenant_id=tenant_id,
            jurisdiction="",
            timestamp=ts,
            action_verb=action_verb,
            resource_type="tenant_registry",
            resource_id=resource_id,
            before_state=before,
            after_state=after,
            correlation_id="",
            previous_event_hash=previous,
        )
        await self._audit.emit(
            AuditEvent(
                actor=actor,
                tenant_id=tenant_id,
                jurisdiction="",
                action_verb=action_verb,
                resource_type="tenant_registry",
                resource_id=resource_id,
                before_state=before,
                after_state=after,
                correlation_id="",
                previous_event_hash=previous,
                this_event_hash=this_hash,
                timestamp=ts,
            )
        )


def _row_to_tenant(row) -> Tenant:
    """Manual row→domain construction.

    Frozen-dataclass-plus-Core pattern (D34). The adapter owns the
    impedance mismatch; the domain stays pure and unmutated.
    """
    return Tenant(
        id=TenantId(str(row["tenant_id"])),
        jurisdiction=Jurisdiction(row["jurisdiction"]),
        display_name=row["display_name"],
        credentials=EncryptedCredentials(
            wrapped_dek=bytes(row["wrapped_dek"]),
            ciphertext=bytes(row["ciphertext"]),
            aad=bytes(row["aad"]),
        ),
        status=TenantStatus(row["status"]),
        created_at=row["created_at"],
    )
