"""Tenant-isolation contract test for the authored CDD layer (D24 / D63 / D200, S102).

Red-team-verifies that the new authored node types (:Intermediary, :External,
and the extended :Lever) honour property-based tenant scoping through the
``TenantScopedNeo4jSession`` wrapper: tenant A writes an authored element on a
goal; tenant B's read of the same goal returns none of it. Also asserts the
authored constraints exist on the live shape (the live-surface verification law).

Runs inside the ``padhanam-api`` container so the ``padhanam-neo4j`` Compose
hostname resolves over the internal network (the S5 host-port-binding rule);
skips cleanly when the stack is not reachable.
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
            capture_output=True, timeout=5, check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return False
    return True


def _services_running(*names: str) -> bool:
    proc = subprocess.run(
        ["docker", "compose", "ps", "--services", "--filter", "status=running"],
        capture_output=True, text=True, check=False,
    )
    return set(names).issubset(set(proc.stdout.split()))


@pytest.fixture(scope="module")
def stack_ready() -> None:
    if not _docker_available():
        pytest.skip("docker compose not reachable from test environment")
    if not _services_running("padhanam-api", "padhanam-neo4j"):
        pytest.skip("padhanam-api and padhanam-neo4j must be running")


def _exec_in_api(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "padhanam-api", "python", "-c", script],
        capture_output=True, text=True, timeout=60, check=False,
    )


def test_authored_cdd_read_isolation_across_tenants(stack_ready: None) -> None:
    """Tenant A writes an authored intermediary on a goal; tenant B's read of the
    same goal returns no elements (the WHERE-tenant_id predicate filters A's)."""
    script = r"""
import asyncio, sys
from uuid import uuid4
from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
from shared_kernel import TenantContext
from padhanam.config import Neo4jSettings

A = TenantContext(tenant_id="00000000-0000-4000-8000-00000000a001",
                  jurisdiction="eu-west", cost_attribution_id="00000000-0000-4000-8000-00000000a001")
B = TenantContext(tenant_id="00000000-0000-4000-8000-00000000b002",
                  jurisdiction="eu-west", cost_attribution_id="00000000-0000-4000-8000-00000000b002")

async def main():
    repo = Neo4jGraphRepository.from_settings(Neo4jSettings())
    outcome_id = uuid4()
    element_id = uuid4()
    try:
        await repo.merge_authored_element(
            tenant_context=A, outcome_id=outcome_id, element_kind="intermediary",
            element_id=element_id, label="isolation-probe",
            provenance_origin="llm_drafted", proof_state="pending",
        )
        own = await repo.read_authored_cdd(tenant_context=A, outcome_id=outcome_id)
        if not any(e.element_id == element_id for e in own.elements):
            print("FAIL: tenant A could not read its own authored element"); return 1
        other = await repo.read_authored_cdd(tenant_context=B, outcome_id=outcome_id)
        if other.elements:
            print("FAIL: tenant B read tenant A's authored elements: " + str(other.elements)); return 2
    finally:
        # Clean up A's probe (user-initiated delete path).
        await repo.delete_authored_element(tenant_context=A, element_kind="intermediary", element_id=element_id)
        await repo.close()
    print("OK"); return 0

sys.exit(asyncio.run(main()))
"""
    result = _exec_in_api(script)
    assert result.returncode == 0, (
        f"exit {result.returncode}: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "OK" in result.stdout


def test_authored_constraints_exist_on_the_live_shape(stack_ready: None) -> None:
    """The migration's authored constraints exist on the running Neo4j (the
    live-surface verification law — drift fails here, not in production)."""
    script = r"""
import asyncio, sys
from contexts.ingestion.adapters.outbound.neo4j.graph_repository import Neo4jGraphRepository
from neo4j import AsyncGraphDatabase
from padhanam.config import Neo4jSettings

async def main():
    s = Neo4jSettings()
    driver = AsyncGraphDatabase.driver(s.bolt_uri, auth=(s.user, s.password))
    want = {"intermediary_unique_per_tenant", "external_unique_per_tenant", "lever_id_unique_per_tenant"}
    try:
        async with driver.session() as sess:
            res = await sess.run("SHOW CONSTRAINTS YIELD name RETURN name")
            names = {r["name"] async for r in res}
    finally:
        await driver.close()
    missing = want - names
    if missing:
        print("FAIL: missing constraints: " + str(missing)); return 1
    print("OK"); return 0

sys.exit(asyncio.run(main()))
"""
    result = _exec_in_api(script)
    assert result.returncode == 0, (
        f"exit {result.returncode}: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "OK" in result.stdout
