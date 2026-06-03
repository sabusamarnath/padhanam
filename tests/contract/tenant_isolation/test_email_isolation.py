"""Tenant isolation contract for the email substrate (D24, D151, S56a).

The email tables are tenant-scoped per database-per-tenant (D32). The
Postgres adapters carry bound-tenant defence-in-depth: an adapter bound to
tenant A rejects any call carrying tenant B's TenantContext before session
resolution, mirroring the calendar and portfolio adapters. The live path
is exercised at the S56a smoke; these scenarios pin the structural
invariant without a database.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from shared_kernel import TenantContext, TenantId

from contexts.email.adapters.outbound.postgres.connection_repository import (
    PostgresConnectionRepository,
)
from contexts.email.adapters.outbound.postgres.email_store import (
    PostgresEmailChunkStore,
    PostgresEmailStore,
)
from contexts.email.domain.connection import Connection
from contexts.email.domain.email import Email
from contexts.email.domain.email_chunk import EmailChunk

_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
_TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _ctx(tenant: str) -> TenantContext:
    return TenantContext(tenant_id=tenant, jurisdiction="eu-west", cost_attribution_id=tenant)


async def _unreachable_resolver(_tid: TenantId) -> object:  # noqa: ARG001
    raise AssertionError("resolver must not be reached on bound-tenant reject")


def _email(tenant: str) -> Email:
    return Email(
        id=uuid4(), tenant_id=UUID(tenant), jurisdiction="eu-west", message_id="m1",
        thread_id=None, from_address=None, to_addresses=(), cc_addresses=(), subject="x",
        body="y", snippet=None, received_at=_NOW, labels=(), history_id=None,
        content_hash="h", created_at=_NOW, updated_at=_NOW,
    )


def test_email_store_rejects_cross_tenant_upsert() -> None:
    store = PostgresEmailStore(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId(_TENANT_A),
    )
    with pytest.raises(ValueError):
        asyncio.run(store.upsert_email(tenant_context=_ctx(_TENANT_B), email=_email(_TENANT_B)))


def test_email_store_rejects_cross_tenant_read() -> None:
    store = PostgresEmailStore(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId(_TENANT_A),
    )
    with pytest.raises(ValueError):
        asyncio.run(store.get_by_message_id(tenant_context=_ctx(_TENANT_B), message_id="m1"))


def test_email_store_rejects_cross_tenant_set_diff_scope() -> None:
    store = PostgresEmailStore(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId(_TENANT_A),
    )
    with pytest.raises(ValueError):
        asyncio.run(
            store.list_live_message_ids_in_window(tenant_context=_ctx(_TENANT_B), window_start=_NOW)
        )


def test_email_chunk_store_rejects_cross_tenant_replace() -> None:
    store = PostgresEmailChunkStore(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId(_TENANT_A),
    )
    chunk = EmailChunk(id=uuid4(), email_id=uuid4(), message_id="m1", chunk_index=0, content="c")
    with pytest.raises(ValueError):
        asyncio.run(
            store.replace_chunks(
                tenant_context=_ctx(_TENANT_B), email_id=uuid4(), message_id="m1",
                chunks=[(chunk, [0.1] * 768)],
            )
        )


def test_email_connection_repo_rejects_cross_tenant() -> None:
    repo = PostgresConnectionRepository(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId(_TENANT_A),
    )
    conn = Connection(
        id=uuid4(), tenant_id=UUID(_TENANT_B), jurisdiction="eu-west", provider="google_mail",
        provider_config_key="google-mail", provider_connection_ref="ref",
        created_at=_NOW, updated_at=_NOW,
    )
    with pytest.raises(ValueError):
        asyncio.run(repo.save_connection(tenant_context=_ctx(_TENANT_B), connection=conn))
