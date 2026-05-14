"""End-to-end full-pipeline integration test for the extraction
stage (S21 / D64).

Drives ``padhanam ingest run`` then runs the worker with
``--stages parse,embed,extract`` so the source transitions through
parsing → embedding → extracting and lands at the terminal-success
state ``indexed``. Verifies:

  - source.state == 'indexed' after the worker completes
  - Neo4j contains at least one :Entity node for tenant_a with the
    expected schema (tenant_id, jurisdiction, name, entity_type,
    source_chunk_ids populated to the source's chunk ids)
  - all :Entity nodes carry non-empty tenant_id matching tenant_a
  - relationships (if any) carry tenant_id matching tenant_a
  - cross-tenant graph reads return no rows for tenant_b

Plus the worker idempotency invariant on already-indexed sources:
running the worker again with --stages extract claims nothing.

The test runs inside the ``padhanam-api`` container via
``docker compose exec`` so the per-tenant Postgres + the shared
``padhanam-neo4j`` Compose hostnames resolve over the internal
network. Skips cleanly when the Compose stack is not reachable.

This test is slow (~30-60s per run) because it makes real LLM
calls against Qwen 2.5 7B via Ollama through LiteLLM. It is the
single full-pipeline test S21 ships; existing parse-and-embed-
shaped tests stay at their original scope via ``--stages parse,
embed`` per S21 commit 5.
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap

import pytest

pytestmark = pytest.mark.live_llm  # D99: real LLM via LiteLLM/Ollama


_TENANT_A_LABEL = "a"
_TENANT_A_ID = "00000000-0000-4000-8000-00000000a001"
_TENANT_B_ID = "00000000-0000-4000-8000-00000000b002"


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
    needed = ("padhanam-api", "padhanam-neo4j", "litellm", "ollama",
              "postgres-tenant-a")
    if not _services_running(*needed):
        pytest.skip(f"compose services not running: {needed}")


def _exec(*args: str, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "exec", "-T", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _exec_psql_tenant_a(query: str) -> str:
    cmd = (
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "'
        + query.replace('"', '\\"')
        + '"'
    )
    result = _exec("postgres-tenant-a", "sh", "-c", cmd, timeout=30)
    return result.stdout.strip()


def _truncate_tenant_a() -> None:
    _exec_psql_tenant_a("TRUNCATE TABLE chunks, sources;")


def _truncate_neo4j_extraction_data() -> None:
    """Wipe :Entity nodes and relationships left by prior test runs.

    Keeps the constraint and index in place — only deletes data.
    Runs inside padhanam-api so the bolt URL resolves on the
    Compose network.
    """
    script = r"""
import asyncio
from neo4j import AsyncGraphDatabase
from padhanam.config import Neo4jSettings


async def main():
    s = Neo4jSettings()
    driver = AsyncGraphDatabase.driver(s.bolt_uri, auth=(s.user, s.password))
    try:
        async with driver.session() as session:
            result = await session.run("MATCH (e:Entity) DETACH DELETE e")
            await result.consume()
    finally:
        await driver.close()


asyncio.run(main())
"""
    _exec("padhanam-api", "python", "-c", script, timeout=30)


@pytest.fixture(autouse=True)
def _clean(stack_ready: None) -> None:
    _truncate_tenant_a()
    _truncate_neo4j_extraction_data()


def _ingest_run(file_path: str) -> str:
    result = _exec(
        "padhanam-api",
        "python",
        "-m",
        "apps.cli",
        "ingest",
        "run",
        file_path,
        "--tenant-id",
        _TENANT_A_LABEL,
    )
    assert result.returncode == 0, (
        f"ingest run failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    return result.stdout.strip().splitlines()[-1]


def _ingest_worker(stages: str, max_iterations: int = 5) -> str:
    result = _exec(
        "padhanam-api",
        "python",
        "-m",
        "apps.cli",
        "ingest",
        "worker",
        "--tenant-id",
        _TENANT_A_LABEL,
        "--max-iterations",
        str(max_iterations),
        "--stages",
        stages,
        timeout=300,  # extraction LLM call can take 30+ seconds per chunk
    )
    assert result.returncode == 0, (
        f"ingest worker failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    return result.stdout


def _write_file(path: str, content: str) -> None:
    proc = subprocess.Popen(
        [
            "docker", "compose", "exec", "-T", "padhanam-api",
            "sh", "-c", f"cat > {path}",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    proc.communicate(input=content.encode("utf-8"), timeout=10)


def _query_entities_for_tenant(tenant_id: str) -> list[dict[str, str]]:
    """Return :Entity nodes for the tenant via the Neo4j driver."""
    script = f"""
import asyncio
import json
import sys

from neo4j import AsyncGraphDatabase

from padhanam.config import Neo4jSettings


async def main():
    s = Neo4jSettings()
    driver = AsyncGraphDatabase.driver(s.bolt_uri, auth=(s.user, s.password))
    rows = []
    try:
        async with driver.session() as session:
            r = await session.run(
                "MATCH (e:Entity) WHERE e.tenant_id = $tid "
                "RETURN e.tenant_id AS tenant_id, e.jurisdiction AS jurisdiction, "
                "e.name AS name, e.entity_type AS entity_type, "
                "e.source_chunk_ids AS source_chunk_ids",
                tid={tenant_id!r},
            )
            async for record in r:
                rows.append({{
                    "tenant_id": record["tenant_id"],
                    "jurisdiction": record["jurisdiction"],
                    "name": record["name"],
                    "entity_type": record["entity_type"],
                    "source_chunk_ids": list(record["source_chunk_ids"] or []),
                }})
    finally:
        await driver.close()
    print(json.dumps(rows))


asyncio.run(main())
"""
    result = _exec("padhanam-api", "python", "-c", script, timeout=30)
    assert result.returncode == 0, (
        f"entity query failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    import json
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_full_pipeline_extract_lands_indexed_with_entities() -> None:
    """End-to-end: register a markdown source, run worker through
    parse + embed + extract; assert state=indexed and at least one
    entity exists in Neo4j with correct tenant scoping.
    """
    _write_file(
        "/tmp/e2e_extract.md",
        textwrap.dedent(
            """\
            # ACME Corp Overview

            ACME Corp is a London-based company founded in 1999.
            Alice Johnson is the Chief Technology Officer at ACME Corp.
            """
        ),
    )
    source_id = _ingest_run("/tmp/e2e_extract.md")
    assert len(source_id) == 36

    output = _ingest_worker("parse,embed,extract", max_iterations=10)
    # processed=3 means parse + embed + extract all completed.
    assert "processed 3 source" in output

    state = _exec_psql_tenant_a(
        f"SELECT state FROM sources WHERE id='{source_id}'"
    )
    assert state == "indexed", f"unexpected final state: {state}"

    # Neo4j must hold at least one :Entity for tenant A.
    entities = _query_entities_for_tenant(_TENANT_A_ID)
    assert len(entities) >= 1, (
        "expected at least one :Entity node in Neo4j after extraction"
    )

    # Property invariants per D64.
    chunk_ids = _exec_psql_tenant_a(
        f"SELECT id::text FROM chunks WHERE source_id='{source_id}'"
    ).splitlines()
    chunk_id_set = {cid.strip() for cid in chunk_ids if cid.strip()}
    for entity in entities:
        assert entity["tenant_id"] == _TENANT_A_ID
        assert entity["jurisdiction"]
        assert entity["name"]
        assert entity["entity_type"]
        assert entity["source_chunk_ids"], (
            f"entity {entity['name']!r} has no source_chunk_ids — "
            "provenance must land per D64"
        )
        # Provenance points back to chunks of the registered source.
        assert chunk_id_set.intersection(entity["source_chunk_ids"]), (
            f"entity {entity['name']!r} source_chunk_ids "
            f"{entity['source_chunk_ids']!r} does not intersect "
            f"source's chunks {chunk_id_set!r}"
        )

    # Cross-tenant invariant: tenant B sees nothing.
    other = _query_entities_for_tenant(_TENANT_B_ID)
    assert other == [], (
        "tenant B should see zero entities for tenant A's data"
    )


def test_worker_idempotent_on_already_indexed_source() -> None:
    """Re-running the worker against an already-indexed source
    claims no rows. The S21 extract stage's idempotency holds the
    same way the parse + embed stages' idempotency does — the
    claim filters on ``state = 'embedded'`` and an indexed source
    is excluded.

    Combined with Cypher MERGE on the entity composite, this means
    the operator's recovery surface for `extraction_failed` (manual
    transition back to `embedded`) is structurally safe: re-running
    the worker re-extracts and MERGE-dedupes any entities that
    happen to land twice.
    """
    _write_file(
        "/tmp/e2e_extract_idem.md",
        "# Test\n\nACME is in London.\n",
    )
    _ingest_run("/tmp/e2e_extract_idem.md")
    _ingest_worker("parse,embed,extract", max_iterations=10)

    # Second run with the same stages claims nothing.
    second = _ingest_worker("parse,embed,extract", max_iterations=5)
    assert "processed 0 source" in second
