"""Unit tests for the Neo4j retrieval adapter (S22 / D65).

The adapter composes a per-tenant Postgres lookup of indexed
chunk_ids with a tenant-scoped Cypher traversal via the
TenantScopedNeo4jSession wrapper. Behavioural assertions (cross-
tenant traversal returns zero results, depth limit honoured under
real Cypher) live in the e2e integration test at commit 6; this
module fences the adapter's composition shape.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Sequence
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from contexts.ingestion.adapters.outbound.retrieval.neo4j_traverse import (
    Neo4jTraverse,
)
from shared_kernel import TenantContext


_TENANT_A = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)


def _make_pg_session_factory(chunk_ids: list[UUID]):
    """Return a factory whose async session.execute -> result.scalars().all()
    yields the supplied chunk_id strings, mimicking the chunks-by-state SQL.
    Captures the SQL params in ``captured``.
    """
    captured: dict[str, object] = {}

    class _FakeResult:
        def scalars(self):
            class _S:
                def all(self_inner):
                    return [str(cid) for cid in chunk_ids]

            return _S()

    class _FakeSession:
        async def execute(self_inner, statement, params=None):
            captured["params"] = params
            captured["statement"] = statement
            return _FakeResult()

        async def __aenter__(self_inner):
            return self_inner

        async def __aexit__(self_inner, *args):
            return None

    def factory():
        return _FakeSession()

    return factory, captured


def _make_neo4j_driver_returning(records: list[dict]) -> MagicMock:
    """Build a driver whose tenant-scoped session traverse returns
    the supplied Cypher record dicts.
    """
    session = MagicMock()
    result = MagicMock()
    result.data = AsyncMock(return_value=records)
    session.run = AsyncMock(return_value=result)
    session.close = AsyncMock()
    driver = MagicMock()
    driver.session = MagicMock(return_value=session)
    return driver


def test_traverse_returns_empty_when_no_indexed_chunks_for_tenant() -> None:
    """The readiness predicate excludes everything when no source
    has reached indexed state; the adapter short-circuits before
    issuing the Cypher traversal.
    """
    pg_factory, _ = _make_pg_session_factory([])
    driver = _make_neo4j_driver_returning([])
    adapter = Neo4jTraverse(driver=driver, pg_session_factory=pg_factory)

    result = asyncio.run(
        adapter.traverse_graph(seed="ACME Corp", scope=_TENANT_A, depth=2)
    )

    assert result == []
    assert driver.session.call_count == 0


def test_traverse_passes_indexed_chunk_ids_into_cypher() -> None:
    """The Postgres pre-query's chunk_ids land as a Cypher parameter
    so the traversal's readiness predicate can apply them.
    """
    chunk_id_a = uuid4()
    chunk_id_b = uuid4()
    pg_factory, pg_captured = _make_pg_session_factory(
        [chunk_id_a, chunk_id_b]
    )
    driver = _make_neo4j_driver_returning([])
    adapter = Neo4jTraverse(driver=driver, pg_session_factory=pg_factory)

    asyncio.run(
        adapter.traverse_graph(seed="ACME Corp", scope=_TENANT_A, depth=1)
    )

    # PG pre-query parameter shape:
    assert pg_captured["params"]["tenant_id"] == _TENANT_A.tenant_id
    assert pg_captured["params"]["indexed_state"] == "indexed"

    # Neo4j traversal parameter shape: indexed_chunk_ids carry both.
    neo_call = driver.session.return_value.run.call_args
    neo_params = neo_call.args[1]
    assert set(neo_params["indexed_chunk_ids"]) == {
        str(chunk_id_a),
        str(chunk_id_b),
    }
    assert neo_params["seed_name"] == "ACME Corp"
    assert neo_params["tenant_id"] == _TENANT_A.tenant_id


def test_traverse_maps_records_to_entity_results() -> None:
    """Each Cypher record maps to an EntityResult with the
    relationship-type sequence preserved.
    """
    chunk_id = uuid4()
    pg_factory, _ = _make_pg_session_factory([chunk_id])
    records = [
        {
            "tenant_id": _TENANT_A.tenant_id,
            "jurisdiction": _TENANT_A.jurisdiction,
            "name": "ACME Corp",
            "entity_type": "Organisation",
            "source_chunk_ids": [str(chunk_id)],
            "relationship_path": [],
            "created_at": datetime(2026, 5, 7, tzinfo=timezone.utc),
        },
        {
            "tenant_id": _TENANT_A.tenant_id,
            "jurisdiction": _TENANT_A.jurisdiction,
            "name": "Alice",
            "entity_type": "Person",
            "source_chunk_ids": [str(chunk_id)],
            "relationship_path": ["EMPLOYS"],
            "created_at": datetime(2026, 5, 7, tzinfo=timezone.utc),
        },
    ]
    driver = _make_neo4j_driver_returning(records)
    adapter = Neo4jTraverse(driver=driver, pg_session_factory=pg_factory)

    result = asyncio.run(
        adapter.traverse_graph(seed="ACME Corp", scope=_TENANT_A, depth=1)
    )

    assert len(result) == 2
    seed = result[0]
    assert seed.name == "ACME Corp"
    assert seed.relationship_path == ()
    assert seed.source_chunk_ids == (chunk_id,)
    neighbour = result[1]
    assert neighbour.name == "Alice"
    assert neighbour.relationship_path == ("EMPLOYS",)


def test_traverse_handles_null_relationship_path_record() -> None:
    """Some Cypher returns may surface ``relationship_path = None`` if
    the path is empty in unusual cases. The adapter coerces to an
    empty tuple rather than passing None through to EntityResult.
    """
    chunk_id = uuid4()
    pg_factory, _ = _make_pg_session_factory([chunk_id])
    records = [
        {
            "tenant_id": _TENANT_A.tenant_id,
            "jurisdiction": _TENANT_A.jurisdiction,
            "name": "ACME Corp",
            "entity_type": "Organisation",
            "source_chunk_ids": [str(chunk_id)],
            "relationship_path": None,
            "created_at": datetime(2026, 5, 7, tzinfo=timezone.utc),
        },
    ]
    driver = _make_neo4j_driver_returning(records)
    adapter = Neo4jTraverse(driver=driver, pg_session_factory=pg_factory)

    result = asyncio.run(
        adapter.traverse_graph(seed="ACME Corp", scope=_TENANT_A, depth=0)
    )

    assert result[0].relationship_path == ()


def test_traverse_rejects_negative_depth() -> None:
    pg_factory, _ = _make_pg_session_factory([])
    driver = _make_neo4j_driver_returning([])
    adapter = Neo4jTraverse(driver=driver, pg_session_factory=pg_factory)

    with pytest.raises(ValueError, match="non-negative"):
        asyncio.run(
            adapter.traverse_graph(
                seed="anything", scope=_TENANT_A, depth=-1
            )
        )
