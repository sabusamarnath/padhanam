"""Wiring tests for RunHistoryReaderAdapter (S33 commit 4, D97).

The adapter is the apps/cli wiring shape at composition-root altitude
for the run-history read surface; it constructs a per-call
PostgresRunHistoryReader bound to the request's tenant and delegates
to it. These tests verify:

1. The adapter implements the RunHistoryReader Protocol (structural
   satisfaction).
2. The session_factory_for_tenant callable is invoked with the
   right TenantContext on each method call.
3. get_run and list_runs_with_filters delegate to the per-call
   reader correctly.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

from apps.cli._cross_context import RunHistoryReaderAdapter
from contexts.run_history.domain.query_filters import (
    RunListCursor,
    RunListFilters,
)
from contexts.run_history.ports.reader import RunHistoryReader
from shared_kernel import TenantContext


_TENANT_UUID = UUID("aaaa1111-2222-4333-8444-555555555555")


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_UUID,
        jurisdiction="eu-west",
        cost_attribution_id=str(_TENANT_UUID),
    )


class _RecordingSessionContext:
    async def __aenter__(self) -> "_RecordingSession":
        return _RecordingSession()

    async def __aexit__(self, *args: Any) -> None:
        pass


class _RecordingSession:
    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        return _EmptyResult()


class _EmptyResult:
    def first(self) -> None:
        return None

    def all(self) -> list:
        return []


class _RecordingSessionmaker:
    def __call__(self) -> _RecordingSessionContext:
        return _RecordingSessionContext()


def test_adapter_implements_run_history_reader_protocol() -> None:
    """Structural Protocol satisfaction: the adapter exposes the two
    methods RunHistoryReader requires."""
    calls: list[TenantContext] = []

    async def _session_factory(tc: TenantContext) -> _RecordingSessionmaker:
        calls.append(tc)
        return _RecordingSessionmaker()

    adapter = RunHistoryReaderAdapter(
        session_factory_for_tenant=_session_factory,
    )

    # Protocol satisfaction is structural; isinstance with Protocol
    # works because RunHistoryReader is a runtime_checkable-equivalent
    # via duck typing. Verify by attribute existence.
    assert hasattr(adapter, "get_run")
    assert hasattr(adapter, "list_runs_with_filters")
    assert callable(adapter.get_run)
    assert callable(adapter.list_runs_with_filters)


def test_get_run_invokes_session_factory_with_tenant_context() -> None:
    """The session factory is called with the request's TenantContext
    on each get_run invocation."""
    calls: list[TenantContext] = []

    async def _session_factory(tc: TenantContext) -> _RecordingSessionmaker:
        calls.append(tc)
        return _RecordingSessionmaker()

    adapter = RunHistoryReaderAdapter(
        session_factory_for_tenant=_session_factory,
    )

    result = asyncio.run(
        adapter.get_run(tenant_context=_ctx(), run_id=uuid4())
    )

    assert result is None  # The recording session returns no rows.
    assert len(calls) == 1
    assert calls[0].tenant_id == _TENANT_UUID


def test_list_runs_with_filters_invokes_session_factory_with_tenant_context() -> None:
    """The session factory is called once on each list invocation."""
    calls: list[TenantContext] = []

    async def _session_factory(tc: TenantContext) -> _RecordingSessionmaker:
        calls.append(tc)
        return _RecordingSessionmaker()

    adapter = RunHistoryReaderAdapter(
        session_factory_for_tenant=_session_factory,
    )

    page = asyncio.run(
        adapter.list_runs_with_filters(
            tenant_context=_ctx(),
            filters=RunListFilters(),
            cursor=None,
        )
    )

    assert page.runs == ()
    assert page.next_cursor is None
    assert len(calls) == 1
    assert calls[0].tenant_id == _TENANT_UUID
