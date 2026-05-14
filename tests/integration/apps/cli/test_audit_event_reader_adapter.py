"""Wiring tests for AuditEventReaderAdapter (S36 commit 5, D102).

The adapter is the apps/cli wiring shape at composition-root
altitude for the audit read surface; it constructs a per-call
PostgresAuditEventReader closed over the request's tenant
context plus the control-plane sessionmaker held at adapter
construction. These tests verify:

1. The adapter implements the AuditEventReader Protocol
   (structural satisfaction over three methods).
2. The session_factory_for_tenant callable is invoked with the
   right TenantContext on per_tenant destination calls.
3. The control-plane destination calls do NOT invoke the
   per-tenant session factory.
4. AuditQueryRoutingError surfaces through the adapter when
   destination/tenant_context disagree.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest

from apps.cli._cross_context import AuditEventReaderAdapter
from contexts.audit.domain.query_filters import AuditEventListFilters
from contexts.audit.ports.reader import (
    AuditEventReader,
    AuditQueryRoutingError,
)
from shared_kernel import TenantContext


_TENANT_UUID = UUID("aaaa1111-2222-4333-8444-555555555555")


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_UUID,
        jurisdiction="eu-west",
        cost_attribution_id=str(_TENANT_UUID),
    )


class _RecordingMappings:
    def all(self) -> list:
        return []

    def first(self) -> None:
        return None


class _RecordingResult:
    def mappings(self) -> _RecordingMappings:
        return _RecordingMappings()


class _RecordingSession:
    def __init__(self, owner: "_RecordingSessionmaker") -> None:
        self._owner = owner

    async def execute(self, *args: Any, **kwargs: Any) -> _RecordingResult:
        self._owner.executed_statements += 1
        return _RecordingResult()


class _RecordingSessionContext:
    def __init__(self, owner: "_RecordingSessionmaker") -> None:
        self._owner = owner

    async def __aenter__(self) -> _RecordingSession:
        return _RecordingSession(self._owner)

    async def __aexit__(self, *args: Any) -> None:
        pass


class _RecordingSessionmaker:
    def __init__(self) -> None:
        self.executed_statements = 0

    def __call__(self) -> _RecordingSessionContext:
        return _RecordingSessionContext(self)


def test_adapter_satisfies_reader_protocol_shape() -> None:
    cp = _RecordingSessionmaker()

    async def _session_factory(tc: TenantContext) -> _RecordingSessionmaker:
        return _RecordingSessionmaker()

    adapter = AuditEventReaderAdapter(
        session_factory_for_tenant=_session_factory,
        control_plane_sessionmaker=cp,
    )
    for method_name in (
        "get_audit_event",
        "list_audit_events_with_filters",
        "verify_chain_segment",
    ):
        assert hasattr(adapter, method_name)
        assert callable(getattr(adapter, method_name))


def test_per_tenant_get_invokes_session_factory_with_tenant_context() -> None:
    cp = _RecordingSessionmaker()
    calls: list[TenantContext] = []

    async def _session_factory(tc: TenantContext) -> _RecordingSessionmaker:
        calls.append(tc)
        return _RecordingSessionmaker()

    adapter = AuditEventReaderAdapter(
        session_factory_for_tenant=_session_factory,
        control_plane_sessionmaker=cp,
    )

    result = asyncio.run(
        adapter.get_audit_event(
            destination="per_tenant",
            event_id=uuid4(),
            tenant_context=_ctx(),
        )
    )

    assert result is None
    assert len(calls) == 1
    assert calls[0].tenant_id == _TENANT_UUID
    # control-plane sessionmaker was not touched on a per-tenant call
    assert cp.executed_statements == 0


def test_control_plane_get_uses_control_plane_sessionmaker_only() -> None:
    cp = _RecordingSessionmaker()
    calls: list[TenantContext] = []

    async def _session_factory(tc: TenantContext) -> _RecordingSessionmaker:
        calls.append(tc)
        return _RecordingSessionmaker()

    adapter = AuditEventReaderAdapter(
        session_factory_for_tenant=_session_factory,
        control_plane_sessionmaker=cp,
    )

    result = asyncio.run(
        adapter.get_audit_event(
            destination="control_plane",
            event_id=uuid4(),
            tenant_context=None,
        )
    )

    assert result is None
    # per-tenant session factory NOT invoked on a control-plane call
    assert calls == []
    # control-plane sessionmaker executed one statement
    assert cp.executed_statements == 1


def test_list_per_tenant_invokes_session_factory_with_tenant_context() -> None:
    cp = _RecordingSessionmaker()
    calls: list[TenantContext] = []

    async def _session_factory(tc: TenantContext) -> _RecordingSessionmaker:
        calls.append(tc)
        return _RecordingSessionmaker()

    adapter = AuditEventReaderAdapter(
        session_factory_for_tenant=_session_factory,
        control_plane_sessionmaker=cp,
    )

    page = asyncio.run(
        adapter.list_audit_events_with_filters(
            destination="per_tenant",
            filters=AuditEventListFilters(),
            cursor=None,
            page_size=10,
            tenant_context=_ctx(),
        )
    )

    assert page.events == ()
    assert page.next_cursor is None
    assert page.chain_integrity.status == "partial"  # empty page
    assert len(calls) == 1
    assert calls[0].tenant_id == _TENANT_UUID


def test_routing_error_surfaces_per_tenant_without_context() -> None:
    cp = _RecordingSessionmaker()

    async def _session_factory(tc: TenantContext) -> _RecordingSessionmaker:
        return _RecordingSessionmaker()

    adapter = AuditEventReaderAdapter(
        session_factory_for_tenant=_session_factory,
        control_plane_sessionmaker=cp,
    )

    async def run() -> None:
        with pytest.raises(AuditQueryRoutingError, match="per_tenant"):
            await adapter.get_audit_event(
                destination="per_tenant",
                event_id=uuid4(),
                tenant_context=None,
            )

    asyncio.run(run())


def test_routing_error_surfaces_control_plane_with_context() -> None:
    cp = _RecordingSessionmaker()

    async def _session_factory(tc: TenantContext) -> _RecordingSessionmaker:
        return _RecordingSessionmaker()

    adapter = AuditEventReaderAdapter(
        session_factory_for_tenant=_session_factory,
        control_plane_sessionmaker=cp,
    )

    async def run() -> None:
        with pytest.raises(AuditQueryRoutingError, match="control_plane"):
            await adapter.get_audit_event(
                destination="control_plane",
                event_id=uuid4(),
                tenant_context=_ctx(),
            )

    asyncio.run(run())
