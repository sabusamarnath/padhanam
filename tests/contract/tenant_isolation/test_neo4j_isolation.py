"""Tenant-isolation contract test for the Neo4j graph store
(D24 / D63).

Property-based scoping at the data layer plus the
``TenantScopedNeo4jSession`` wrapper at the routing layer make
property-based scoping defensible at audit; this test red-team-
verifies the discipline holds against both reads and writes,
mirroring the harness shape D24 commits to and the existing
postgres-side isolation test at
``test_ingestion_isolation.py``.

Three properties under test:

  1. **Write isolation through the wrapper.** Tenant A's session
     attempts to merge an entity with tenant B's tenant_id; the
     wrapper's tenant-binding validation raises ValueError so the
     write never reaches Neo4j.

  2. **Read isolation through the wrapper.** Tenant A creates an
     entity through its own bound session; tenant B's bound
     session, querying the same chunk_ids, returns an empty
     sequence because the WHERE-tenant_id predicate filters out
     tenant A's row.

  3. **No untenanted entities exist.** A direct Cypher query
     against the shared instance returns zero entities or
     relationships with empty or null tenant_id; the schema
     invariant from D64 holds across the live state.

The test runs inside the ``padhanam-api`` container via
``docker compose exec`` so the ``padhanam-neo4j`` Compose hostname
resolves over the internal network (the S5 host-port-binding rule
keeps Neo4j off the host). Skips cleanly when the Compose stack is
not reachable.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(
            ["docker", "compose", "ps", "-q"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return False
    return True


def _services_running(*names: str) -> bool:
    proc = subprocess.run(
        ["docker", "compose", "ps", "--services", "--filter", "status=running"],
        capture_output=True,
        text=True,
        check=False,
    )
    running = set(proc.stdout.split())
    return set(names).issubset(running)


@pytest.fixture(scope="module")
def stack_ready() -> None:
    if not _docker_available():
        pytest.skip("docker compose not reachable from test environment")
    if not _services_running("padhanam-api", "padhanam-neo4j"):
        pytest.skip("padhanam-api and padhanam-neo4j must be running")


def _exec_in_api(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "padhanam-api", "python", "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_neo4j_wrapper_rejects_cross_tenant_write(stack_ready: None) -> None:
    """Tenant A's wrapper refuses to write an entity carrying
    tenant B's tenant_id; the GraphRepository adapter raises
    GraphRepositoryConfigurationError (translation of the
    wrapper's ValueError per the adapter's exception map)."""
    script = r"""
import asyncio
import sys
from datetime import datetime, timezone
from uuid import uuid4

from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
from contexts.ingestion.domain.entity import Entity
from contexts.ingestion.ports.graph_repository_port import (
    GraphRepositoryConfigurationError,
)
from shared_kernel import TenantContext
from padhanam.config import Neo4jSettings


TENANT_A = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)
TENANT_B_ID = "00000000-0000-4000-8000-00000000b002"


async def main():
    repo = Neo4jGraphRepository.from_settings(Neo4jSettings())
    cross_tenant = Entity(
        tenant_id=TENANT_B_ID,
        jurisdiction="eu-west",
        name="Hostile",
        entity_type="Organisation",
        source_chunk_ids=(uuid4(),),
        created_at=datetime.now(tz=timezone.utc),
    )
    try:
        await repo.merge_entities([cross_tenant], TENANT_A)
        print("FAIL: cross-tenant write was accepted")
        return 1
    except GraphRepositoryConfigurationError as e:
        if "does not match bound tenant" not in str(e):
            print("FAIL: wrong error message: " + str(e))
            return 2
    finally:
        await repo.close()
    print("OK")
    return 0


sys.exit(asyncio.run(main()))
"""
    result = _exec_in_api(script)
    assert result.returncode == 0, (
        f"unexpected exit {result.returncode}: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    assert "OK" in result.stdout


def test_neo4j_read_isolation_across_tenants(stack_ready: None) -> None:
    """Tenant A creates an entity via its bound session; tenant B's
    bound session, querying the same chunk id, returns empty
    because the WHERE-tenant_id predicate filters tenant A's row.
    """
    script = r"""
import asyncio
import sys
from datetime import datetime, timezone
from uuid import uuid4

from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
from contexts.ingestion.domain.entity import Entity
from shared_kernel import TenantContext
from padhanam.config import Neo4jSettings


TENANT_A = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)
TENANT_B = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000b002",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000b002",
)


async def main():
    repo = Neo4jGraphRepository.from_settings(Neo4jSettings())
    chunk_id = uuid4()
    # Use a unique name so the test is repeatable against a shared
    # Neo4j without colliding with prior runs.
    unique_name = f"isolation-probe-{chunk_id}"
    entity_a = Entity(
        tenant_id=TENANT_A.tenant_id,
        jurisdiction=TENANT_A.jurisdiction,
        name=unique_name,
        entity_type="Probe",
        source_chunk_ids=(chunk_id,),
        created_at=datetime.now(tz=timezone.utc),
    )
    try:
        await repo.merge_entities([entity_a], TENANT_A)

        # Tenant A reads its own entity.
        own_view = await repo.get_entities_by_chunk_ids([chunk_id], TENANT_A)
        if len(own_view) != 1 or own_view[0].name != unique_name:
            print(f"FAIL: tenant A could not read its own entity; got {own_view!r}")
            return 1

        # Tenant B reads the same chunk_id and sees nothing.
        other_view = await repo.get_entities_by_chunk_ids([chunk_id], TENANT_B)
        if len(other_view) != 0:
            print(f"FAIL: tenant B saw tenant A's entity: {other_view!r}")
            return 2
    finally:
        await repo.close()
    print("OK")
    return 0


sys.exit(asyncio.run(main()))
"""
    result = _exec_in_api(script)
    assert result.returncode == 0, (
        f"unexpected exit {result.returncode}: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    assert "OK" in result.stdout


def test_neo4j_no_untenanted_entities_or_relationships(
    stack_ready: None,
) -> None:
    """Schema invariant from D64: every :Entity node and every
    relationship carries a non-empty tenant_id. A direct cypher
    query (running through the wrapper for consistency, though the
    invariant is a property of the schema rather than the wrapper)
    returns zero rows for the negative-predicate query.
    """
    script = r"""
import asyncio
import sys

from neo4j import AsyncGraphDatabase

from padhanam.config import Neo4jSettings


async def main():
    settings = Neo4jSettings()
    driver = AsyncGraphDatabase.driver(
        settings.bolt_uri,
        auth=(settings.user, settings.password),
    )
    try:
        async with driver.session() as session:
            r = await session.run(
                "MATCH (e:Entity) "
                "WHERE e.tenant_id IS NULL OR e.tenant_id = '' "
                "RETURN count(e) AS n"
            )
            entity_breach = (await r.single())["n"]
            r = await session.run(
                "MATCH ()-[rel]->() "
                "WHERE rel.tenant_id IS NULL OR rel.tenant_id = '' "
                "RETURN count(rel) AS n"
            )
            rel_breach = (await r.single())["n"]
    finally:
        await driver.close()
    if entity_breach > 0:
        print(f"FAIL: {entity_breach} untenanted :Entity nodes")
        return 1
    if rel_breach > 0:
        print(f"FAIL: {rel_breach} untenanted relationships")
        return 2
    print("OK")
    return 0


sys.exit(asyncio.run(main()))
"""
    result = _exec_in_api(script)
    assert result.returncode == 0, (
        f"unexpected exit {result.returncode}: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    assert "OK" in result.stdout
