"""Unit tests for the TenantScopedNeo4jSession wrapper (S21 / D63).

The wrapper is the single Cypher-execution surface for the
ingestion context per D63. Tests verify, with the AsyncDriver and
AsyncSession mocked at the module-import boundary:

  - Cypher templates carry ``$tenant_id`` from the bound context;
    cross-tenant writes (entity or relationship whose tenant_id
    does not match the bound context) raise ValueError.
  - Relationship-type validation rejects non-Cypher-identifier
    inputs at the wrapper boundary so the dynamic format-
    substitution into the MERGE template stays safe.
  - The wrapper is a no-op on empty input (no driver call made).
  - Reads return the domain shape (Entity / Relationship); the
    wrapper translates the driver's record dicts into the domain
    types.

The integration tests at
``tests/integration/contexts/ingestion/`` and the contract test at
``tests/contract/tenant_isolation/test_neo4j_isolation.py`` exercise
the wrapper against the real Neo4j 5 Community service.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from contexts.ingestion.adapters.outbound.neo4j.session import (
    TenantScopedNeo4jSession,
)
from contexts.ingestion.domain.entity import Entity
from contexts.ingestion.domain.relationship import EntityRef, Relationship
from shared_kernel import TenantContext


_TENANT_A = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)

_TENANT_B = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000b002",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000b002",
)


def _mock_driver() -> tuple[MagicMock, MagicMock]:
    """Construct a mocked AsyncDriver whose ``session()`` returns
    a mocked AsyncSession with ``run`` and ``close`` as awaitables.
    Returns the driver and the session mocks so tests can introspect
    invocations.
    """
    session = MagicMock()
    session.run = AsyncMock()
    session.close = AsyncMock()
    driver = MagicMock()
    driver.session = MagicMock(return_value=session)
    return driver, session


def test_merge_entities_binds_bound_tenant_id_into_cypher_params() -> None:
    driver, session = _mock_driver()
    entity = Entity(
        tenant_id=_TENANT_A.tenant_id,
        jurisdiction="eu-west",
        name="ACME Corp",
        entity_type="Organisation",
        source_chunk_ids=(UUID("00000000-0000-0000-0000-000000000001"),),
        created_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT_A) as s:
            await s.merge_entities([entity])

    asyncio.run(run())

    assert session.run.call_count == 1
    call = session.run.call_args
    params = call.args[1]
    assert params["tenant_id"] == _TENANT_A.tenant_id
    assert params["name"] == "ACME Corp"
    assert params["entity_type"] == "Organisation"
    assert params["source_chunk_ids"] == ["00000000-0000-0000-0000-000000000001"]


def test_merge_entities_rejects_cross_tenant_entity_with_value_error() -> None:
    driver, _ = _mock_driver()
    cross_tenant_entity = Entity(
        tenant_id=_TENANT_B.tenant_id,  # bound is tenant A
        jurisdiction="eu-west",
        name="Hostile",
        entity_type="Organisation",
    )

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT_A) as s:
            await s.merge_entities([cross_tenant_entity])

    with pytest.raises(ValueError, match="does not match bound tenant"):
        asyncio.run(run())


def test_merge_relationships_binds_tenant_and_validates_type() -> None:
    driver, session = _mock_driver()
    rel = Relationship(
        tenant_id=_TENANT_A.tenant_id,
        jurisdiction="eu-west",
        source=EntityRef(name="ACME Corp", entity_type="Organisation"),
        target=EntityRef(name="Alice", entity_type="Person"),
        relationship_type="EMPLOYS",
        source_chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
    )

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT_A) as s:
            await s.merge_relationships([rel])

    asyncio.run(run())

    assert session.run.call_count == 1
    cypher = session.run.call_args.args[0]
    params = session.run.call_args.args[1]
    assert "`EMPLOYS`" in cypher
    assert params["tenant_id"] == _TENANT_A.tenant_id
    assert params["source_chunk_id"] == "00000000-0000-0000-0000-000000000001"


def test_merge_relationships_rejects_non_identifier_relationship_type() -> None:
    driver, _ = _mock_driver()
    bad_rel = Relationship(
        tenant_id=_TENANT_A.tenant_id,
        jurisdiction="eu-west",
        source=EntityRef(name="A", entity_type="X"),
        target=EntityRef(name="B", entity_type="Y"),
        relationship_type="EMPLOYS`); DROP DATABASE neo4j;//",
        source_chunk_id=uuid4(),
    )

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT_A) as s:
            await s.merge_relationships([bad_rel])

    with pytest.raises(ValueError, match="not a valid Cypher identifier"):
        asyncio.run(run())


def test_merge_entities_no_op_on_empty_input() -> None:
    driver, session = _mock_driver()

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT_A) as s:
            await s.merge_entities([])

    asyncio.run(run())

    assert session.run.call_count == 0


def test_merge_relationships_no_op_on_empty_input() -> None:
    driver, session = _mock_driver()

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT_A) as s:
            await s.merge_relationships([])

    asyncio.run(run())

    assert session.run.call_count == 0


def test_get_entities_by_chunk_ids_returns_domain_entities() -> None:
    driver, session = _mock_driver()
    chunk_id = UUID("00000000-0000-0000-0000-000000000001")
    record = {
        "tenant_id": _TENANT_A.tenant_id,
        "jurisdiction": "eu-west",
        "name": "ACME Corp",
        "entity_type": "Organisation",
        "source_chunk_ids": [str(chunk_id)],
        "created_at": datetime(2026, 5, 7, tzinfo=timezone.utc),
    }
    result_obj = MagicMock()
    result_obj.data = AsyncMock(return_value=[record])
    session.run = AsyncMock(return_value=result_obj)

    async def run() -> list[Entity]:
        async with TenantScopedNeo4jSession(driver, _TENANT_A) as s:
            return list(await s.get_entities_by_chunk_ids([chunk_id]))

    entities = asyncio.run(run())

    assert len(entities) == 1
    e = entities[0]
    assert e.tenant_id == _TENANT_A.tenant_id
    assert e.name == "ACME Corp"
    assert e.entity_type == "Organisation"
    assert e.source_chunk_ids == (chunk_id,)
    assert e.created_at == datetime(2026, 5, 7, tzinfo=timezone.utc)
    # Verify the Cypher params carry the bound tenant.
    params = session.run.call_args.args[1]
    assert params["tenant_id"] == _TENANT_A.tenant_id
    assert params["chunk_ids"] == [str(chunk_id)]


def test_get_entities_by_chunk_ids_no_op_on_empty_input() -> None:
    driver, session = _mock_driver()

    async def run() -> list[Entity]:
        async with TenantScopedNeo4jSession(driver, _TENANT_A) as s:
            return list(await s.get_entities_by_chunk_ids([]))

    result = asyncio.run(run())

    assert result == []
    assert session.run.call_count == 0


def test_session_used_outside_context_manager_raises() -> None:
    driver, _ = _mock_driver()
    s = TenantScopedNeo4jSession(driver, _TENANT_A)

    async def run() -> None:
        await s.merge_entities([
            Entity(
                tenant_id=_TENANT_A.tenant_id,
                jurisdiction="eu-west",
                name="X",
                entity_type="Y",
            )
        ])

    with pytest.raises(RuntimeError, match="used outside `async with` block"):
        asyncio.run(run())


# ---------------------------------------------------------------------------
# S22 / D65: traverse_from_seed wrapper-level tests.
# ---------------------------------------------------------------------------


def _mock_driver_with_traversal_records(records: list[dict]) -> tuple[MagicMock, MagicMock]:
    """Build a driver whose run() returns a result whose .data() yields
    the supplied records (the shape Cypher Result.data() returns).
    """
    session = MagicMock()
    result = MagicMock()
    result.data = AsyncMock(return_value=records)
    session.run = AsyncMock(return_value=result)
    session.close = AsyncMock()
    driver = MagicMock()
    driver.session = MagicMock(return_value=session)
    return driver, session


def test_traverse_from_seed_binds_bound_tenant_id_and_indexed_chunk_ids() -> None:
    chunk_id = uuid4()
    driver, session = _mock_driver_with_traversal_records([])

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT_A) as s:
            await s.traverse_from_seed(
                seed_name="ACME Corp",
                depth=2,
                indexed_chunk_ids=[chunk_id],
            )

    asyncio.run(run())

    assert session.run.call_count == 1
    call = session.run.call_args
    cypher = call.args[0]
    params = call.args[1]
    assert "$tenant_id" in cypher
    assert "$indexed_chunk_ids" in cypher
    assert "[*0..2]" in cypher  # depth interpolated literally
    assert params["tenant_id"] == _TENANT_A.tenant_id
    assert params["seed_name"] == "ACME Corp"
    assert params["indexed_chunk_ids"] == [str(chunk_id)]


def test_traverse_from_seed_returns_empty_for_empty_indexed_chunk_ids() -> None:
    """The readiness predicate excludes everything when no source has
    reached indexed state; the wrapper short-circuits without
    issuing a Cypher query.
    """
    driver, session = _mock_driver_with_traversal_records([])

    async def run() -> list:
        async with TenantScopedNeo4jSession(driver, _TENANT_A) as s:
            return list(
                await s.traverse_from_seed(
                    seed_name="anything",
                    depth=1,
                    indexed_chunk_ids=[],
                )
            )

    rows = asyncio.run(run())
    assert rows == []
    assert session.run.call_count == 0


def test_traverse_from_seed_rejects_negative_depth() -> None:
    driver, _ = _mock_driver_with_traversal_records([])

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT_A) as s:
            await s.traverse_from_seed(
                seed_name="x", depth=-1, indexed_chunk_ids=[uuid4()]
            )

    with pytest.raises(ValueError, match="non-negative"):
        asyncio.run(run())


def test_traverse_from_seed_rejects_depth_above_max() -> None:
    driver, _ = _mock_driver_with_traversal_records([])

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT_A) as s:
            await s.traverse_from_seed(
                seed_name="x", depth=999, indexed_chunk_ids=[uuid4()]
            )

    with pytest.raises(ValueError, match="exceeds maximum"):
        asyncio.run(run())
