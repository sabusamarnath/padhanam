"""End-to-end retrieval integration test (S22 / D65).

Drives the full ingestion pipeline (``padhanam ingest run`` → worker
through parse + embed + extract → ``indexed`` state), then exercises
both retrieval surfaces:

  - ``padhanam ingest search "<query>"`` runs vector cosine retrieval
    against the per-tenant chunks table via the HNSW index from S20.
  - ``padhanam ingest traverse "<seed>"`` runs graph traversal from
    the seed entity through the shared Neo4j instance.

Verifies (acceptance criteria 4, 5, 6, 7, 10, 11):

  - Both retrieval methods return non-empty, tenant-scoped results
    after the source reaches indexed state.
  - Cross-tenant retrieval against tenant B returns zero results
    from tenant A's source for both methods (tenant_isolation).
  - Sources in non-``indexed`` states do not surface in retrieval.
  - The OTel span emitted by the query-embedding LiteLLM call
    carries the seven D27/D49/D50 attributes plus the four
    ``gen_ai.cost.*`` attributes (cost-attribution path verified).
  - The ChunkEmbedder's task parameter exercises both call sites:
    DOCUMENT at ingestion (the worker), QUERY at retrieval (this
    test's `padhanam ingest search` invocation).

Slow because the full pipeline runs (parse + embed + extract via
the LLM, then query-embed + retrieval). Skips cleanly when the
Compose stack is not reachable. The test runs inside the
``padhanam-api`` container so per-tenant Postgres + the shared
Neo4j Compose hostnames resolve over the internal network.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap

import pytest

pytestmark = pytest.mark.live_llm  # D99: real LLM via LiteLLM/Ollama


_TENANT_A_LABEL = "a"
_TENANT_B_LABEL = "b"
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
    needed = (
        "padhanam-api", "padhanam-neo4j", "litellm", "ollama",
        "postgres-tenant-a", "postgres-tenant-b",
    )
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


def _exec_psql_tenant(label: str, query: str) -> str:
    cmd = (
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "'
        + query.replace('"', '\\"')
        + '"'
    )
    result = _exec(f"postgres-tenant-{label}", "sh", "-c", cmd, timeout=30)
    return result.stdout.strip()


def _truncate_tenant(label: str) -> None:
    # Include run_chunk_citations in the truncate set: S32 introduced
    # run_chunk_citations.chunk_id REFERENCES chunks(id) ON DELETE SET
    # NULL per D95. TRUNCATE bypasses FK-action triggers; truncating
    # chunks alone fails on the FK reference. Explicit-list shape
    # mirrors S35b at test_concurrent_workers.py; this site was outside
    # S35b's explicit scope at the time per S38a reconciliation.
    _exec_psql_tenant(
        label, "TRUNCATE TABLE chunks, sources, run_chunk_citations;"
    )


def _truncate_neo4j_extraction_data() -> None:
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
    _truncate_tenant(_TENANT_A_LABEL)
    _truncate_tenant(_TENANT_B_LABEL)
    _truncate_neo4j_extraction_data()


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


def _ingest_run(label: str, file_path: str) -> str:
    result = _exec(
        "padhanam-api", "python", "-m", "apps.cli",
        "ingest", "run", file_path, "--tenant-id", label,
    )
    assert result.returncode == 0, (
        f"ingest run failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    return result.stdout.strip().splitlines()[-1]


def _ingest_worker(label: str, stages: str, max_iterations: int = 10) -> str:
    result = _exec(
        "padhanam-api", "python", "-m", "apps.cli",
        "ingest", "worker",
        "--tenant-id", label,
        "--max-iterations", str(max_iterations),
        "--stages", stages,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"ingest worker failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    return result.stdout


def _ingest_search(label: str, query: str, limit: int = 5) -> str:
    result = _exec(
        "padhanam-api", "python", "-m", "apps.cli",
        "ingest", "search", query,
        "--tenant-id", label,
        "--limit", str(limit),
        timeout=120,
    )
    assert result.returncode == 0, (
        f"ingest search failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    return result.stdout


def _ingest_traverse(label: str, seed: str, depth: int = 2) -> str:
    result = _exec(
        "padhanam-api", "python", "-m", "apps.cli",
        "ingest", "traverse", seed,
        "--tenant-id", label,
        "--depth", str(depth),
        timeout=60,
    )
    assert result.returncode == 0, (
        f"ingest traverse failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    return result.stdout


def _setup_indexed_source(label: str, content: str) -> str:
    """Register a source for the tenant and run the worker through to
    indexed. Returns the source id.
    """
    path = f"/tmp/e2e_retrieval_{label}.md"
    _write_file(path, content)
    source_id = _ingest_run(label, path)
    output = _ingest_worker(label, stages="parse,embed,extract")
    assert "processed 3 source" in output
    state = _exec_psql_tenant(
        label, f"SELECT state FROM sources WHERE id='{source_id}'"
    )
    assert state == "indexed", f"setup did not reach indexed: {state}"
    return source_id


_TENANT_A_CORPUS = textwrap.dedent(
    """\
    # ACME Corp Overview

    ACME Corp is a London-based company founded in 1999.
    Alice Johnson is the Chief Technology Officer at ACME Corp.

    ## Locations

    The company has offices in London and New York. The London
    office is the headquarters.
    """
)


def test_search_returns_chunks_for_indexed_tenant_source(
    stack_ready: None,
) -> None:
    """search_vector against tenant A returns non-empty chunks once
    the source is indexed (acceptance criteria 4).
    """
    _setup_indexed_source(_TENANT_A_LABEL, _TENANT_A_CORPUS)
    output = _ingest_search(_TENANT_A_LABEL, "Where is ACME headquartered?")
    assert "(no results)" not in output
    # Output contains the rank-prefix shape and at least one
    # similarity score line.
    assert "similarity=" in output


def test_traverse_returns_entities_for_indexed_tenant_source(
    stack_ready: None,
) -> None:
    """traverse_graph against tenant A returns non-empty entities
    once the source is indexed (acceptance criteria 4).
    """
    _setup_indexed_source(_TENANT_A_LABEL, _TENANT_A_CORPUS)
    # Try several plausible seed names — Qwen 2.5 7B's extraction
    # may surface "ACME Corp", "ACME", "Acme Corp", etc., and we
    # don't want the test to fail on prompt-output drift. Seed-not-
    # found returns an empty sequence.
    for seed in ("ACME Corp", "ACME", "Acme Corp", "Acme"):
        output = _ingest_traverse(_TENANT_A_LABEL, seed, depth=2)
        if "(no results)" not in output:
            break
    else:
        pytest.fail(
            "traverse returned (no results) for every plausible ACME seed; "
            "either the extractor produced no entities or the seed name "
            "drifted unexpectedly"
        )
    # The seed itself should surface with path=(seed) per the CLI
    # rendering of an empty relationship_path.
    assert "path=" in output


def test_cross_tenant_search_returns_zero_for_other_tenant(
    stack_ready: None,
) -> None:
    """Tenant A indexes a source; tenant B's search returns nothing.
    Defence-in-depth: per-tenant Postgres topology (D32) makes
    cross-tenant retrieval structurally impossible at the database
    level; the WHERE-clause tenant filter is the application-layer
    backstop verified here (acceptance criteria 6).
    """
    _setup_indexed_source(_TENANT_A_LABEL, _TENANT_A_CORPUS)
    # Tenant B has no sources, so search returns no rows.
    output = _ingest_search(_TENANT_B_LABEL, "ACME Corp")
    assert "(no results)" in output


def test_cross_tenant_traverse_returns_zero_for_other_tenant(
    stack_ready: None,
) -> None:
    """Same shape as the search cross-tenant test but for graph
    traversal. The TenantScopedNeo4jSession wrapper auto-binds the
    tenant_id predicate; tenant B sees nothing of tenant A's
    extracted graph (acceptance criteria 6).
    """
    _setup_indexed_source(_TENANT_A_LABEL, _TENANT_A_CORPUS)
    output = _ingest_traverse(_TENANT_B_LABEL, "ACME Corp", depth=2)
    assert "(no results)" in output


def test_search_excludes_non_indexed_sources(stack_ready: None) -> None:
    """A source in ``embedded`` (not yet ``indexed``) state does not
    surface in vector retrieval. Drives the worker only through
    parse + embed; the source state lands at ``embedded``; search
    returns no rows (acceptance criteria 7).
    """
    _write_file("/tmp/e2e_partial.md", _TENANT_A_CORPUS)
    source_id = _ingest_run(_TENANT_A_LABEL, "/tmp/e2e_partial.md")
    # Drain only parse + embed — extraction stays untouched, source
    # state stops at 'embedded'.
    _ingest_worker(_TENANT_A_LABEL, stages="parse,embed", max_iterations=5)
    state = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT state FROM sources WHERE id='{source_id}'",
    )
    assert state == "embedded", f"expected embedded, got {state}"

    output = _ingest_search(_TENANT_A_LABEL, "ACME Corp")
    # The chunks exist and have embeddings, but the source is not
    # ``indexed`` so the readiness filter excludes them. Without
    # this filter the search would return rows; with it, none.
    assert "(no results)" in output


def test_query_embedding_emits_cost_attribution_span(
    stack_ready: None,
) -> None:
    """Cost-attribution path verified per D41 / D49 / D50: the
    LiteLLM embedder emits an OTel span on the query-side
    embedding call carrying the seven tenant + GenAI attributes
    plus the four ``gen_ai.cost.*`` attributes. Same shape as the
    S20 corpus-side embedding call (acceptance criteria 10).

    Captures the span via the in-memory exporter inside the
    padhanam-api container, mirroring the
    ``test_embedder_cost_capture_e2e.py`` shape.
    """
    script = r"""
import asyncio
import json
import sys

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from contexts.ingestion.adapters.outbound.embedding import (
    LiteLLMChunkEmbedder,
)
from contexts.ingestion.domain.embedding_task import EmbeddingTask
from shared_kernel import TenantContext


TENANT_A = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)


async def main():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    embedder = LiteLLMChunkEmbedder()
    vec = await embedder.embed_query("hello", TENANT_A, EmbeddingTask.QUERY)
    if len(vec) != 768:
        print(json.dumps({"error": "wrong vector length", "len": len(vec)}))
        return 1

    spans = exporter.get_finished_spans()
    if not spans:
        print(json.dumps({"error": "no spans captured"}))
        return 2
    span = spans[-1]
    attrs = dict(span.attributes)
    needed = [
        "gen_ai.system",
        "gen_ai.request.model",
        "gen_ai.operation.name",
        "tenant.id",
        "tenant.jurisdiction",
        "tenant.cost_attribution_id",
        "padhanam.embedding.task",
        "gen_ai.cost.input_usd",
        "gen_ai.cost.output_usd",
        "gen_ai.cost.total_usd",
        "gen_ai.cost.pricing_status",
    ]
    missing = [k for k in needed if k not in attrs]
    if missing:
        print(json.dumps({"error": "missing attrs", "missing": missing}))
        return 3
    if attrs["padhanam.embedding.task"] != "query":
        print(json.dumps({"error": "wrong task", "task": attrs["padhanam.embedding.task"]}))
        return 4
    if attrs["tenant.id"] != TENANT_A.tenant_id:
        print(json.dumps({"error": "wrong tenant", "tenant.id": attrs["tenant.id"]}))
        return 5
    print(json.dumps({"ok": True, "task": attrs["padhanam.embedding.task"]}))
    return 0


sys.exit(asyncio.run(main()))
"""
    result = _exec("padhanam-api", "python", "-c", script, timeout=60)
    assert result.returncode == 0, (
        f"cost-attribution probe failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    last_line = result.stdout.strip().splitlines()[-1]
    payload = json.loads(last_line)
    assert payload.get("ok") is True, f"cost-attribution check failed: {payload!r}"
    assert payload["task"] == "query"
