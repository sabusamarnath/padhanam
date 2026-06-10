"""Unit tests for ops.sync_calendar multi-connection iteration (S78, D176).

The script extended from a single-connection pull (LIMIT 1, S77) to iterating
every google_calendar connection (D176 permits a second account). This asserts
the iteration builds and refreshes the adapter once per connection, each with
that connection's own id — which is the calendar_id sync_calendar stamps and
scopes by (S74), so one calendar's pull never cross-writes another's rows.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from ops.sync_calendar import sync_all_connections


class _FakeAdapter:
    def __init__(self, connection_id: UUID) -> None:
        self.connection_id = connection_id
        self.refreshed_with: object | None = None

    async def refresh(self, *, tenant_context: object) -> str:
        self.refreshed_with = tenant_context
        return f"synced:{self.connection_id}"


def test_sync_all_connections_pulls_each_scoped_by_its_own_id() -> None:
    built: list[tuple[str, UUID]] = []
    adapters: dict[UUID, _FakeAdapter] = {}

    def build_adapter(*, tenant_id: str, connection_id: UUID) -> _FakeAdapter:
        built.append((tenant_id, connection_id))
        adapter = _FakeAdapter(connection_id)
        adapters[connection_id] = adapter
        return adapter

    personal = UUID("00000000-0000-4000-8000-0000000000a1")
    work = UUID("00000000-0000-4000-8000-0000000000b2")
    ctx = object()

    results = asyncio.run(
        sync_all_connections(
            tenant_id="t",
            tenant_context=ctx,
            connection_ids=[personal, work],
            build_adapter=build_adapter,
        )
    )

    # Both connections were pulled (not just the first, the LIMIT-1 regression),
    # each adapter built with its OWN connection id = its calendar_id (D176/S74).
    assert [cid for _, cid in built] == [personal, work]
    assert adapters[personal].refreshed_with is ctx
    assert adapters[work].refreshed_with is ctx
    # Each result is tagged with its own connection id — the per-connection
    # scoping that makes the pull cross-write-free.
    assert results == [
        (personal, f"synced:{personal}"),
        (work, f"synced:{work}"),
    ]


def test_sync_all_connections_empty_is_a_noop() -> None:
    calls: list[object] = []

    def build_adapter(*, tenant_id: str, connection_id: UUID) -> object:
        calls.append(connection_id)
        raise AssertionError("must not build an adapter for zero connections")

    results = asyncio.run(
        sync_all_connections(
            tenant_id="t",
            tenant_context=object(),
            connection_ids=[],
            build_adapter=build_adapter,
        )
    )
    assert results == []
    assert calls == []
