"""Live guard + tenant isolation for the S103c correction loop (D203).

On real Neo4j: tenant A relinks a unit's evidence to a different element (the edge
moves, the unit is marked user-owned), and a re-match-shaped delete
(``replace_element_evidence`` with an empty set) **keeps the user-owned unit's
edge** while deleting a non-owned unit's edge — correction precedence proven on
the live surface. Tenant B reads none of A's evidence. The append-only correction
capture is unit-tested (the audit emit); this guard proves the graph guarantees.

Runs inside ``padhanam-api`` (the S5 host-port rule); skips when the stack is down.
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


def test_relink_marks_owned_and_rematch_respects_it_and_isolates(
    stack_ready: None,
) -> None:
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
    oid = uuid4(); lev1 = uuid4(); lev2 = uuid4(); u_corr = uuid4(); u_plain = uuid4()
    try:
        for lid, label in ((lev1, "corr-lever-1"), (lev2, "corr-lever-2")):
            await repo.merge_authored_element(
                tenant_context=A, outcome_id=oid, element_kind="lever",
                element_id=lid, label=label,
                provenance_origin="user_authored", proof_state="accepted")
        async with TenantScopedNeo4jSession(repo._driver, A) as s:
            for uid in (u_corr, u_plain):
                await s._bound_session.run(
                    "MERGE (u:Unit {tenant_id: $t, unit_id: $u}) ON CREATE SET u.jurisdiction='eu-west'",
                    {"t": str(A.tenant_id), "u": str(uid)})
        # Both units bound to lev1 by the matcher.
        await repo.replace_element_evidence(tenant_context=A, evidence=[
            ElementEvidenceWrite(unit_id=u, element_kind="lever", element_id=lev1,
                                 tier="lexical_exact", status="confirmed", basis="element-exact")
            for u in (u_corr, u_plain)])

        # The user relinks u_corr from lev1 to lev2 -> u_corr becomes user-owned.
        ok = await repo.relink_element_evidence(
            tenant_context=A, unit_id=u_corr, from_kind="lever",
            from_element_id=lev1, to_kind="lever", to_element_id=lev2)
        if not ok:
            print("FAIL: relink returned False"); return 1
        owned = await repo.list_user_owned_unit_ids(tenant_context=A)
        if u_corr not in owned or u_plain in owned:
            print("FAIL: ownership wrong: " + str(owned)); return 2

        # A re-match-shaped delete (replace with empty) must keep the owned unit's
        # edge and drop the non-owned unit's edge.
        await repo.replace_element_evidence(tenant_context=A, evidence=[])
        ev = await repo.list_element_evidence(tenant_context=A)
        corr = [e for e in ev if e.unit_id == u_corr]
        plain = [e for e in ev if e.unit_id == u_plain]
        if not corr:
            print("FAIL: re-match overwrote the user's correction"); return 3
        if corr[0].element_id != lev2:
            print("FAIL: correction not at the relink target: " + str(corr[0])); return 4
        if plain:
            print("FAIL: a non-owned unit's edge survived the re-match"); return 5

        other = await repo.list_element_evidence(tenant_context=B)
        if any(e.unit_id in (u_corr, u_plain) for e in other):
            print("FAIL: tenant B read tenant A's evidence"); return 6
    finally:
        # Clear A's owned flag so the cleanup delete removes everything.
        async with TenantScopedNeo4jSession(repo._driver, A) as s:
            await s._bound_session.run(
                "MATCH (u:Unit {tenant_id: $t})-[r:EVIDENCES]->() DELETE r",
                {"t": str(A.tenant_id)})
            for uid in (u_corr, u_plain):
                await s._bound_session.run(
                    "MATCH (u:Unit {tenant_id: $t, unit_id: $u}) DETACH DELETE u",
                    {"t": str(A.tenant_id), "u": str(uid)})
        for lid in (lev1, lev2):
            await repo.delete_authored_element(tenant_context=A, element_kind="lever", element_id=lid)
        await repo.close()
    print("OK"); return 0

sys.exit(asyncio.run(main()))
"""
    result = _exec_in_api(script)
    assert result.returncode == 0, (
        f"exit {result.returncode}: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "OK" in result.stdout
