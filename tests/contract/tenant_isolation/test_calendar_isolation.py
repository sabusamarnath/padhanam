"""Tenant isolation contract for the calendar substrate (D24, D148, S55a).

The connections and meetings tables are tenant-scoped per
database-per-tenant (D32). The Postgres adapters carry bound-tenant
defence-in-depth: an adapter bound to tenant A rejects any call carrying
tenant B's TenantContext before session resolution, mirroring the
portfolio and fired_triggers adapters. The live Postgres path is
exercised at the S55a smoke; these scenarios pin the structural invariant
without a database.

D24 requires every adapter touching tenant-scoped data to ship with
tenant_isolation contract scenarios.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from shared_kernel import TenantContext, TenantId

from contexts.calendar.adapters.outbound.postgres.connection_repository import (
    PostgresConnectionRepository,
)
from contexts.calendar.adapters.outbound.postgres.meeting_store import (
    PostgresMeetingStore,
)
from contexts.calendar.domain.connection import Connection
from contexts.calendar.domain.meeting import Meeting, MeetingStatus

_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=timezone.utc)
_TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _ctx(tenant: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant, jurisdiction="eu-west", cost_attribution_id=tenant
    )


async def _unreachable_resolver(_tenant_id: TenantId) -> object:  # noqa: ARG001
    raise AssertionError("resolver must not be reached on bound-tenant reject")


def _meeting(tenant: str) -> Meeting:
    return Meeting(
        id=uuid4(),
        tenant_id=UUID(tenant),
        jurisdiction="eu-west",
        google_event_id="evt-1",
        status=MeetingStatus.CONFIRMED,
        title="x",
        description=None,
        location=None,
        attendees=(),
        organizer_email=None,
        start_at=None,
        end_at=None,
        start_raw=None,
        end_raw=None,
        source_updated_at=None,
        recurring_event_id=None,
        html_link=None,
        content_hash="h",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _connection(tenant: str) -> Connection:
    return Connection(
        id=uuid4(),
        tenant_id=UUID(tenant),
        jurisdiction="eu-west",
        provider="google_calendar",
        provider_config_key="google-calendar",
        provider_connection_ref="ref",
        created_at=_NOW,
        updated_at=_NOW,
    )


def test_meeting_store_rejects_cross_tenant_upsert() -> None:
    store = PostgresMeetingStore(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId(_TENANT_A),
    )
    with pytest.raises(ValueError, match="does not match adapter's bound tenant"):
        asyncio.run(
            store.upsert_meeting(
                tenant_context=_ctx(_TENANT_B), meeting=_meeting(_TENANT_B)
            )
        )


def test_meeting_store_rejects_cross_tenant_read() -> None:
    store = PostgresMeetingStore(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId(_TENANT_A),
    )
    with pytest.raises(ValueError, match="does not match adapter's bound tenant"):
        asyncio.run(
            store.get_by_event_id(
                tenant_context=_ctx(_TENANT_B), google_event_id="evt-1"
            )
        )


def test_connection_repo_rejects_cross_tenant() -> None:
    repo = PostgresConnectionRepository(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId(_TENANT_A),
    )
    with pytest.raises(ValueError, match="does not match adapter's bound tenant"):
        asyncio.run(
            repo.save_connection(
                tenant_context=_ctx(_TENANT_B), connection=_connection(_TENANT_B)
            )
        )
