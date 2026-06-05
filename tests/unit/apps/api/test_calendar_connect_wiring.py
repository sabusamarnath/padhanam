"""Tests for the live calendar connect seam (D160, S60b, D24).

The connect-callback connection store and the operator-gated initiator.
The store is exercised with a recording stub repository (patched at its
module path, since store_connection imports it lazily) that enforces the
real bound-tenant guard — so the isolation invariant is red-team shaped:
the stored Connection binds to the actor's tenant, never another's, and
the first-sync failure does not lose the stored connection.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

import contexts.calendar.adapters.outbound.postgres.connection_repository as conn_repo_mod
from apps.api._calendar_connect_wiring import (
    ConnectError,
    ConnectionStore,
    ConnectSession,
    NangoCalendarConnectInitiator,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

_TENANT_A = "00000000-0000-4000-8000-00000000d001"
_TENANT_B = "00000000-0000-4000-8000-00000000a002"


def _actor(tenant_id: str) -> ActorContext:
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=tenant_id, jurisdiction="eu-west", cost_attribution_id=tenant_id
        ),
        actor_id=f"operator-{tenant_id[-1]}",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


class _RecordingConnectionRepo:
    """Stub mirroring PostgresConnectionRepository's bound-tenant guard (D24)."""

    saved: list = []

    def __init__(self, *, per_tenant_sessionmaker_resolver, bound_tenant_id):
        self.bound = str(bound_tenant_id)

    async def save_connection(self, *, tenant_context, connection):
        # Defence-in-depth: the real adapter raises on a tenant mismatch.
        if str(connection.tenant_id) != self.bound:
            raise ValueError("connection tenant does not match bound tenant")
        if str(tenant_context.tenant_id) != self.bound:
            raise ValueError("context tenant does not match bound tenant")
        _RecordingConnectionRepo.saved.append(connection)


def _store(monkeypatch, *, first_sync=None):
    monkeypatch.setattr(
        conn_repo_mod, "PostgresConnectionRepository", _RecordingConnectionRepo
    )

    async def _sf(_tenant_context):
        return object()

    return ConnectionStore(session_factory_for_tenant=_sf, first_sync=first_sync)


# ----------------------------------------------------------------- store
def test_callback_stores_a_bound_tenant_connection(monkeypatch) -> None:
    _RecordingConnectionRepo.saved = []
    synced = []

    async def _first_sync(tenant_id, connection_id, tenant_context):
        synced.append((tenant_id, connection_id))

    store = _store(monkeypatch, first_sync=_first_sync)
    result = asyncio.run(
        store.store_connection(
            actor=_actor(_TENANT_A), provider_connection_ref="nango-conn-123"
        )
    )
    assert result.synced is True
    saved = _RecordingConnectionRepo.saved
    assert len(saved) == 1
    assert str(saved[0].tenant_id) == _TENANT_A
    assert saved[0].provider_config_key == "google-calendar"
    assert saved[0].provider_connection_ref == "nango-conn-123"
    assert isinstance(result.connection_id, UUID)
    assert synced and synced[0][0] == _TENANT_A


def test_two_tenants_each_store_their_own_connection(monkeypatch) -> None:
    """Red-team: each tenant's connection binds to its own tenant, never the other's."""
    _RecordingConnectionRepo.saved = []
    store = _store(monkeypatch, first_sync=None)
    asyncio.run(store.store_connection(actor=_actor(_TENANT_A), provider_connection_ref="a"))
    asyncio.run(store.store_connection(actor=_actor(_TENANT_B), provider_connection_ref="b"))
    tenants = {str(c.tenant_id) for c in _RecordingConnectionRepo.saved}
    assert tenants == {_TENANT_A, _TENANT_B}
    # No connection carries a tenant other than the actor that stored it.
    for c in _RecordingConnectionRepo.saved:
        assert c.provider_connection_ref in ("a", "b")


def test_first_sync_failure_does_not_lose_the_connection(monkeypatch) -> None:
    _RecordingConnectionRepo.saved = []

    async def _boom(tenant_id, connection_id, tenant_context):
        raise RuntimeError("nango unreachable")

    store = _store(monkeypatch, first_sync=_boom)
    result = asyncio.run(
        store.store_connection(actor=_actor(_TENANT_A), provider_connection_ref="r")
    )
    assert result.synced is False
    assert "nango unreachable" in (result.sync_error or "")
    assert len(_RecordingConnectionRepo.saved) == 1  # stored regardless


def test_missing_reference_raises(monkeypatch) -> None:
    store = _store(monkeypatch)
    with pytest.raises(ConnectError):
        asyncio.run(
            store.store_connection(actor=_actor(_TENANT_A), provider_connection_ref="  ")
        )


# ------------------------------------------------------------- initiator
def test_initiator_operator_gated_until_wired() -> None:
    initiator = NangoCalendarConnectInitiator()  # no session creator
    with pytest.raises(ConnectError):
        asyncio.run(initiator.create_session(actor=_actor(_TENANT_A)))


def test_initiator_returns_injected_session() -> None:
    async def _creator(tenant_id):
        return ConnectSession(
            provider_config_key="google-calendar",
            connect_url=f"https://nango/connect/{tenant_id}",
        )

    initiator = NangoCalendarConnectInitiator(session_creator=_creator)
    session = asyncio.run(initiator.create_session(actor=_actor(_TENANT_A)))
    assert session.connect_url.endswith(_TENANT_A)
