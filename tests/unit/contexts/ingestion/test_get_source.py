"""Unit tests for the get_source use case (S25).

Read-side application-layer wrapper around
``SourceRepositoryPort.get_source`` shipped at S25 as the cross-
context consumer surface the agent context's
``create_agent_from_methodology`` flow consumes through the apps/cli
SourceLookup adapter.

Exercises the use case logic against an in-memory fake repository.
Adapter behaviour against the live tenant data plane is covered by
the existing ingestion integration tests.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.ingestion.application.get_source import get_source
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState


def _make_source(*, source_id: UUID, tenant_id: str) -> Source:
    now = datetime.now(timezone.utc)
    return Source(
        id=source_id,
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        file_name="test.md",
        file_type="markdown",
        file_size_bytes=10,
        raw_content=b"# test\n\n",
        state=SourceState.RECEIVED,
        parsing_error_text=None,
        created_by_user_id="user-1",
        created_at=now,
        updated_at=now,
    )


class _InMemoryRepo:
    def __init__(self, sources: list[Source] | None = None) -> None:
        self._sources = sources or []

    async def get_source(self, source_id: UUID, tenant_id: str) -> Source | None:
        for s in self._sources:
            if s.id == source_id and s.tenant_id == tenant_id:
                return s
        return None


def _run(coro):
    return asyncio.run(coro)


def test_get_source_returns_source_on_match() -> None:
    sid = uuid4()
    repo = _InMemoryRepo([_make_source(source_id=sid, tenant_id="tenant-a")])
    result = _run(
        get_source(repository=repo, source_id=sid, tenant_id="tenant-a")
    )
    assert result.id == sid
    assert result.tenant_id == "tenant-a"


def test_get_source_raises_lookup_error_when_id_missing() -> None:
    repo = _InMemoryRepo([])
    sid = uuid4()
    with pytest.raises(LookupError) as exc_info:
        _run(
            get_source(repository=repo, source_id=sid, tenant_id="tenant-a")
        )
    assert str(sid) in str(exc_info.value)
    assert "tenant-a" in str(exc_info.value)


def test_get_source_raises_lookup_error_when_tenant_mismatches() -> None:
    """Cross-tenant access returns None from the repository (D24
    tenant isolation), and the use case upgrades that to LookupError.
    Distinguishing missing-id from wrong-tenant would require a
    cross-tenant query that violates tenant isolation, which is the
    structural reason for the unified error."""
    sid = uuid4()
    repo = _InMemoryRepo([_make_source(source_id=sid, tenant_id="tenant-a")])
    with pytest.raises(LookupError):
        _run(
            get_source(repository=repo, source_id=sid, tenant_id="tenant-b")
        )


def test_get_source_returns_full_source_aggregate() -> None:
    """The use case is pure pass-through after the None-to-LookupError
    upgrade; the full Source aggregate flows back to the caller."""
    sid = uuid4()
    src = _make_source(source_id=sid, tenant_id="tenant-a")
    repo = _InMemoryRepo([src])
    result = _run(
        get_source(repository=repo, source_id=sid, tenant_id="tenant-a")
    )
    assert result is src
