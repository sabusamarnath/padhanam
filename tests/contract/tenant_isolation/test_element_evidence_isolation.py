"""Tenant-isolation + live binding guard for the element-evidence edge (D202, S103b).

Red-team-verifies the ``(:Unit)-[:EVIDENCES]->(authored element)`` edge on the
live graph: tenant A writes a unit, an authored lever, and an element-evidence
edge between them; A reads the binding back (element kind + the element's
outcome_id for the derive) and the derived goal edge; tenant B's read of the same
returns none. The live-surface verification law — element binding proven on real
Neo4j, not fixtures.

Runs inside the ``padhanam-api`` container so the ``padhanam-neo4j`` Compose
hostname resolves over the internal network (the S5 host-port-binding rule); skips
cleanly when the stack is not reachable.
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


def test_element_evidence_binds_and_isolates(stack_ready: None) -> None:
    """Tenant A binds a unit to an authored lever via EVIDENCES; A reads the
    binding + the derived goal edge; tenant B reads none (the WHERE-tenant_id
    predicate filters A's)."""
    script = r"""
import asyncio, sys
from uuid import uuid4
from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
from contexts.ingestion.adapters.outbound.neo4j.session import TenantScopedNeo4jSession
from contexts.ingestion.ports.unit_graph_port import ElementEvidenceWrite
from shared_kernel import TenantContext
from padhanam.config import Neo4jSettings

A = TenantContext(tenant_id="00000000-0000-4000-8000-00000000a001",
                  jurisdiction="eu-west", cost_attribution_id="00000000-0000-4000-8000-00000000a001")
B = TenantContext(tenant_id="00000000-0000-4000-8000-00000000b002",
                  jurisdiction="eu-west", cost_attribution_id="00000000-0000-4000-8000-00000000b002")

async def main():
    repo = Neo4jGraphRepository.from_settings(Neo4jSettings())
    outcome_id = uuid4(); lever_id = uuid4(); unit_id = uuid4()
    try:
        # An authored lever on a goal (carries outcome_id for the derive).
        await repo.merge_authored_element(
            tenant_context=A, outcome_id=outcome_id, element_kind="lever",
            element_id=lever_id, label="evidence-probe-lever",
            provenance_origin="user_authored", proof_state="accepted")
        # A :Unit for tenant A (created directly through the wrapper).
        async with TenantScopedNeo4jSession(repo._driver, A) as s:
            await s._bound_session.run(
                "MERGE (u:Unit {tenant_id: $t, unit_id: $u}) "
                "ON CREATE SET u.jurisdiction = $j",
                {"t": str(A.tenant_id), "u": str(unit_id), "j": "eu-west"})

        await repo.replace_element_evidence(tenant_context=A, evidence=[
            ElementEvidenceWrite(unit_id=unit_id, element_kind="lever",
                                 element_id=lever_id, tier="lexical_exact",
                                 status="confirmed", basis="element-exact")])

        own = await repo.list_element_evidence(tenant_context=A)
        mine = [e for e in own if e.unit_id == unit_id and e.element_id == lever_id]
        if not mine:
            print("FAIL: tenant A could not read its own element evidence"); return 1
        if mine[0].element_kind != "lever" or mine[0].outcome_id != outcome_id:
            print("FAIL: binding lost its kind/outcome_id: " + str(mine[0])); return 2

        # The goal level derives from the evidence (one rollup edge to the outcome).
        from contexts.daily_driver.domain.goal_assessment import derive_goal_edges, ElementEvidence
        from contexts.daily_driver.domain.work_unit import LinkStatus
        derived = derive_goal_edges(tuple(
            ElementEvidence(e.unit_id, e.element_kind, e.element_id, e.outcome_id,
                            e.tier, LinkStatus(e.status), e.basis) for e in mine))
        if not derived or derived[0].outcome_id != outcome_id:
            print("FAIL: goal-level derive did not roll up to the outcome"); return 3

        other = await repo.list_element_evidence(tenant_context=B)
        if any(e.unit_id == unit_id for e in other):
            print("FAIL: tenant B read tenant A's element evidence"); return 4
    finally:
        await repo.replace_element_evidence(tenant_context=A, evidence=[])
        await repo.delete_authored_element(tenant_context=A, element_kind="lever", element_id=lever_id)
        async with TenantScopedNeo4jSession(repo._driver, A) as s:
            await s._bound_session.run(
                "MATCH (u:Unit {tenant_id: $t, unit_id: $u}) DETACH DELETE u",
                {"t": str(A.tenant_id), "u": str(unit_id)})
        await repo.close()
    print("OK"); return 0

sys.exit(asyncio.run(main()))
"""
    result = _exec_in_api(script)
    assert result.returncode == 0, (
        f"exit {result.returncode}: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "OK" in result.stdout
