"""Tenant isolation contract test for the ingestion tables (D32 / D60).

Per D32, per-tenant data planes are independent Postgres instances;
control-plane carries operator-owned, jurisdiction-spanning data
only. The two ingestion tables (D60 / D61) live on the per-tenant
track and must exist on each tenant's database; the control-plane
database must not have them.

Asserts the structural invariant directly against running DBs by
shelling out to ``docker compose exec`` and querying
``information_schema.tables`` on each instance — the same shape
the cost-columns and audit-isolation contracts use. Skips cleanly
when the Compose stack is not reachable.

The cross-tenant write/read isolation tests live alongside the
worker integration test at S19 (the Postgres adapter's tenant_id
filter is exercised end-to-end through the worker flow). The
structural test here asserts the schema-level isolation; the
behavioural test asserts the runtime-level isolation.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid

import pytest


_INGESTION_TABLES = (
    "chunks",
    "sources",
)


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


def _exec_psql(service: str, user: str, db: str, query: str) -> str:
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        service,
        "psql",
        "-U",
        user,
        "-d",
        db,
        "-tAc",
        query,
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"psql failed in {service} (exit {result.returncode}):"
            f"\nstderr={result.stderr!r}\nstdout={result.stdout!r}"
        )
    return result.stdout.strip()


@pytest.fixture(scope="module")
def compose_running() -> None:
    if not _docker_available():
        pytest.skip("docker compose not reachable from test environment")
    services = subprocess.run(
        ["docker", "compose", "ps", "--services", "--filter", "status=running"],
        capture_output=True,
        text=True,
        check=False,
    )
    running = set(services.stdout.split())
    needed = {"postgres-control-plane", "postgres-tenant-a", "postgres-tenant-b"}
    if not needed.issubset(running):
        missing = needed - running
        pytest.skip(f"compose services not running: {sorted(missing)}")


def _env(key: str) -> str:
    value = os.environ.get(key)
    if value:
        return value
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1]
    except FileNotFoundError:
        pass
    raise RuntimeError(f"env var {key} not set and not in .env")


def _table_list_query() -> str:
    in_clause = ", ".join(f"'{t}'" for t in _INGESTION_TABLES)
    return (
        "SELECT table_name FROM information_schema.tables "
        f"WHERE table_schema='public' AND table_name IN ({in_clause}) "
        "ORDER BY table_name"
    )


@pytest.mark.parametrize(
    "service,user_env,db_env",
    [
        ("postgres-tenant-a", "POSTGRES_TENANT_A_USER", "POSTGRES_TENANT_A_DB"),
        ("postgres-tenant-b", "POSTGRES_TENANT_B_USER", "POSTGRES_TENANT_B_DB"),
    ],
)
def test_per_tenant_db_has_both_ingestion_tables(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """Positive case for D32 per-tenant track: each tenant's DB
    carries the two ingestion tables.
    """
    user = _env(user_env)
    db = _env(db_env)
    found = set(
        _exec_psql(service, user, db, _table_list_query()).splitlines()
    )
    assert found == set(_INGESTION_TABLES), (
        f"per-tenant DB {service} missing one or more ingestion tables; "
        f"found {sorted(found)}"
    )


def test_control_plane_db_has_no_ingestion_tables(
    compose_running: None,
) -> None:
    """Negative case for D32 instance independence: control-plane DB
    has none of the ingestion tables. Per-tenant data must not leak
    onto the control plane.
    """
    user = _env("POSTGRES_CONTROL_PLANE_USER")
    db = _env("POSTGRES_CONTROL_PLANE_DB")
    found = _exec_psql(
        "postgres-control-plane", user, db, _table_list_query()
    )
    assert found == "", (
        f"control-plane should have no ingestion tables; psql reported "
        f"{found!r}"
    )


@pytest.mark.parametrize(
    "service,user_env,db_env",
    [
        ("postgres-tenant-a", "POSTGRES_TENANT_A_USER", "POSTGRES_TENANT_A_DB"),
        ("postgres-tenant-b", "POSTGRES_TENANT_B_USER", "POSTGRES_TENANT_B_DB"),
    ],
)
def test_sources_state_check_constraint_present(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """Per D60: the sources.state column carries a CHECK constraint
    pinning the type-tag space to the four S19 values. Without the
    CHECK, the worker reentrancy seam is dishonest about its state
    space; future stages that extend the CHECK at S20/S21 can do so
    knowing the floor is enforced at the schema level.
    """
    user = _env(user_env)
    db = _env(db_env)
    query = (
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'sources'::regclass AND contype='c' "
        "AND conname='sources_state_check'"
    )
    found = _exec_psql(service, user, db, query)
    assert found == "sources_state_check", (
        f"sources_state_check missing on {service}; psql reported {found!r}"
    )


@pytest.mark.parametrize(
    "service,user_env,db_env",
    [
        ("postgres-tenant-a", "POSTGRES_TENANT_A_USER", "POSTGRES_TENANT_A_DB"),
        ("postgres-tenant-b", "POSTGRES_TENANT_B_USER", "POSTGRES_TENANT_B_DB"),
    ],
)
def test_chunks_unique_source_chunk_index_present(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """Per D60: chunks(source_id, chunk_index) is UNIQUE so that
    re-running the parser against an already-parsed source produces
    an integrity violation rather than duplicate rows. The
    structural backstop for the worker idempotency contract.
    """
    user = _env(user_env)
    db = _env(db_env)
    query = (
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'chunks'::regclass AND contype='u' "
        "AND conname='chunks_source_chunk_index_unique'"
    )
    found = _exec_psql(service, user, db, query)
    assert found == "chunks_source_chunk_index_unique", (
        f"chunks_source_chunk_index_unique missing on {service}; "
        f"psql reported {found!r}"
    )


@pytest.mark.parametrize(
    "service,user_env,db_env",
    [
        ("postgres-tenant-a", "POSTGRES_TENANT_A_USER", "POSTGRES_TENANT_A_DB"),
        ("postgres-tenant-b", "POSTGRES_TENANT_B_USER", "POSTGRES_TENANT_B_DB"),
    ],
)
def test_pgvector_extension_enabled(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """Per D62: revision 0006 enables the pgvector extension on each
    tenant database so the chunks.embedding vector(768) column and
    the HNSW index over vector_cosine_ops resolve. The pgvector
    Docker image makes the extension available; the extension itself
    needs explicit CREATE per database.
    """
    user = _env(user_env)
    db = _env(db_env)
    query = "SELECT extname FROM pg_extension WHERE extname='vector'"
    found = _exec_psql(service, user, db, query)
    assert found == "vector", (
        f"pgvector extension not enabled on {service}; psql reported "
        f"{found!r}"
    )


@pytest.mark.parametrize(
    "service,user_env,db_env",
    [
        ("postgres-tenant-a", "POSTGRES_TENANT_A_USER", "POSTGRES_TENANT_A_DB"),
        ("postgres-tenant-b", "POSTGRES_TENANT_B_USER", "POSTGRES_TENANT_B_DB"),
    ],
)
def test_chunks_embedding_column_present(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """Per D62: chunks gets a single ``embedding vector(768)`` column
    on each tenant DB via revision 0006. The column is per-tenant per
    D32; the control-plane DB does not carry chunks at all (asserted
    elsewhere in this module).
    """
    user = _env(user_env)
    db = _env(db_env)
    query = (
        "SELECT column_name || ':' || udt_name "
        "FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='chunks' "
        "AND column_name='embedding'"
    )
    found = _exec_psql(service, user, db, query)
    assert found == "embedding:vector", (
        f"chunks.embedding column missing or wrong type on {service}; "
        f"psql reported {found!r}"
    )


@pytest.mark.parametrize(
    "service,user_env,db_env",
    [
        ("postgres-tenant-a", "POSTGRES_TENANT_A_USER", "POSTGRES_TENANT_A_DB"),
        ("postgres-tenant-b", "POSTGRES_TENANT_B_USER", "POSTGRES_TENANT_B_DB"),
    ],
)
def test_chunks_embedding_hnsw_index_present(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """Per D62: an HNSW index over (embedding vector_cosine_ops) lands
    in revision 0006 alongside the column. Without the index, vector
    search degrades to sequential scan; the structural test pins the
    architectural commitment to the HNSW + cosine choice.
    """
    user = _env(user_env)
    db = _env(db_env)
    query = (
        "SELECT indexname FROM pg_indexes "
        "WHERE tablename='chunks' "
        "AND indexname='chunks_embedding_hnsw_idx'"
    )
    found = _exec_psql(service, user, db, query)
    assert found == "chunks_embedding_hnsw_idx", (
        f"chunks_embedding_hnsw_idx missing on {service}; "
        f"psql reported {found!r}"
    )


def test_control_plane_db_has_no_pgvector_extension(
    compose_running: None,
) -> None:
    """The control-plane DB has no embedding columns and no HNSW
    indices, so the pgvector extension does not need to be enabled
    there. This is a positive signal that revision 0006 ran on
    tenants-only per D32, not on control plane.
    """
    user = _env("POSTGRES_CONTROL_PLANE_USER")
    db = _env("POSTGRES_CONTROL_PLANE_DB")
    query = "SELECT extname FROM pg_extension WHERE extname='vector'"
    found = _exec_psql(
        "postgres-control-plane", user, db, query
    )
    assert found == "", (
        f"control-plane DB unexpectedly has pgvector enabled; "
        f"psql reported {found!r}"
    )


# ---------------------------------------------------------------------------
# S22 / D65 — retrieval-surface tenant-isolation contracts.
#
# These tests exercise the application-level retrieval ports against
# both tenants by invoking ``padhanam ingest search`` and
# ``padhanam ingest traverse`` inside the padhanam-api container.
# Cross-tenant retrieval must respect D24's tenant predicate filter.
#
# Fixture-setup pattern at S35b: psql lives in the postgres-tenant
# container image (it's the image's native CLI), not in the padhanam-
# api image; the prior padhanam-api shell-out failed because psql is
# absent there, so the truncate ran nowhere and the tests passed only
# when tenant DBs happened to be empty (S30b's demo runs populated
# chunks; S35a's trace_id-propagation demo did the same — the latent
# pass-because-empty mode surfaced at S35a close as load-bearing).
#
# The methodology-fixture pattern at test_methodology_isolation.py
# uses SQLAlchemy from host loopback against the control-plane Postgres
# (5433 binding, an explicit D5 exception). That pattern does not
# transfer here: per D5 the per-tenant Postgres containers carry no
# host-port bindings by design, so SQLAlchemy-from-host cannot reach
# them. The equivalent in-container psql pattern from
# test_concurrent_workers.py::_exec_psql_tenant_a and
# test_create_from_methodology_flow.py::_exec_psql_tenant — both
# exec'ing psql inside postgres-tenant-<label> — is the structurally
# honest substitute. Same architectural property as the methodology
# fixture's in-container SQL execution, just not in Python. The
# reconciliation finding is preserved in briefs/p9/s35b.md Appendix D.
#
# Red-team posture per D24: each tenant is seeded with a distinct
# marker chunk so the test passes-because-isolated rather than
# pass-because-empty. The search test asserts each tenant returns its
# own marker AND never the other tenant's marker — the (no other
# marker) outcome proves the predicate filter is real, not a side-
# effect of globally-empty tables.
# ---------------------------------------------------------------------------


_TENANT_UUID_BY_LABEL: dict[str, str] = {
    "a": "00000000-0000-4000-8000-00000000a001",
    "b": "00000000-0000-4000-8000-00000000b002",
}
_MARKER_BY_LABEL: dict[str, str] = {
    "a": "ISO_CONTRACT_MARKER_TENANT_A",
    "b": "ISO_CONTRACT_MARKER_TENANT_B",
}
# Unit vector at 768 dimensions (every dimension = 1/sqrt(768)). Any
# query embedding produced by the embedder yields a nonzero cosine
# similarity against this constant, so HNSW returns the seeded chunk
# when its own tenant searches. Cross-tenant search returns nothing
# because the predicate filter excludes the row before HNSW runs.
_UNIT_VAL = round(1 / (768 ** 0.5), 8)
_PLACEHOLDER_EMBEDDING = "[" + ",".join([str(_UNIT_VAL)] * 768) + "]"


def _exec_psql_in_tenant(label: str, sql: str, timeout: int = 30) -> str:
    """Execute SQL inside the postgres-tenant-<label> container via
    docker compose exec. psql is the postgres image's native CLI; this
    is the path the codebase already uses at test_concurrent_workers.py
    and test_create_from_methodology_flow.py."""
    cmd = (
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "'
        + sql.replace('"', '\\"')
        + '"'
    )
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            f"postgres-tenant-{label}",
            "sh",
            "-c",
            cmd,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    return result.stdout.strip()


def _truncate_tenant(label: str) -> None:
    """Truncate per-tenant ingestion tables.

    Includes run_chunk_citations to satisfy the S32 FK boundary per
    D95 (run_chunk_citations.chunk_id REFERENCES chunks(id) ON DELETE
    SET NULL; TRUNCATE bypasses FK-action triggers). Same explicit-
    list shape applied at the commit-2 TRUNCATE+CASCADE fix.
    """
    _exec_psql_in_tenant(
        label, "TRUNCATE TABLE chunks, sources, run_chunk_citations;"
    )


def _seed_marker_chunk(label: str) -> None:
    """Insert one source + one chunk row into postgres-tenant-<label>,
    bypassing the LLM-driven ingestion pipeline. The seeded chunk is
    sufficient signal for the cross-tenant contract: search must
    respect the tenant predicate filter regardless of how rows landed.

    sources.state='indexed' is required so the pgvector_search query's
    ``s.state = :indexed_state`` clause passes the chunk through.
    """
    tenant_uuid = _TENANT_UUID_BY_LABEL[label]
    marker = _MARKER_BY_LABEL[label]
    src_id = str(uuid.uuid4())
    chunk_id = str(uuid.uuid4())
    sql = (
        "INSERT INTO sources "
        "(id, tenant_id, jurisdiction, file_name, file_type, "
        "file_size_bytes, raw_content, state, created_by_user_id) "
        f"VALUES ('{src_id}', '{tenant_uuid}', 'eu-west', "
        f"'iso-marker-{label}.md', 'markdown', 64, "
        "''::bytea, 'indexed', "
        "'tests/contract/tenant_isolation'); "
        "INSERT INTO chunks "
        "(id, source_id, tenant_id, jurisdiction, chunk_index, "
        "content, embedding) "
        f"VALUES ('{chunk_id}', '{src_id}', '{tenant_uuid}', "
        "'eu-west', 0, "
        f"'{marker} fixture-seeded chunk for D24 verification.', "
        f"'{_PLACEHOLDER_EMBEDDING}'::vector);"
    )
    _exec_psql_in_tenant(label, sql, timeout=30)


@pytest.fixture(scope="module")
def red_team_state(compose_running: None) -> "None":
    """Reset per-tenant ingestion state and seed each tenant with one
    marker chunk so cross-tenant isolation tests pass-because-isolated
    rather than pass-because-empty per D24.

    Module-scoped to amortise the setup cost across both retrieval-
    surface tests. Teardown restores empty state so subsequent
    contract tests in the harness start from a known floor.
    """
    for label in ("a", "b"):
        _truncate_tenant(label)
    for label in ("a", "b"):
        _seed_marker_chunk(label)
    yield
    for label in ("a", "b"):
        _truncate_tenant(label)


def _exec_in_api(
    *args: str, timeout: int = 60
) -> subprocess.CompletedProcess[str]:
    """Invoke the padhanam CLI inside the padhanam-api container so the
    per-tenant Postgres hostnames resolve over the Compose network."""
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "padhanam-api", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


@pytest.mark.parametrize("tenant_label", ["a", "b"])
def test_search_returns_only_own_tenant_chunks(
    red_team_state: None, tenant_label: str
) -> None:
    """Cross-tenant non-leak via the search path. Each tenant is
    seeded with a distinct marker chunk at fixture-setup time; the
    test asserts the searching tenant returns its own marker AND
    never the other tenant's marker.

    The (other marker not present) assertion is the load-bearing
    isolation claim: a tenant predicate failure would surface as the
    other tenant's marker leaking into this tenant's result set. The
    test passes because D24's predicate filter holds, not because
    tables happen to be empty.
    """
    own_marker = _MARKER_BY_LABEL[tenant_label]
    other_label = "b" if tenant_label == "a" else "a"
    other_marker = _MARKER_BY_LABEL[other_label]
    result = _exec_in_api(
        "python", "-m", "apps.cli", "ingest", "search",
        "isolation marker", "--tenant-id", tenant_label, "--limit", "5",
    )
    assert result.returncode == 0, (
        f"ingest search failed for tenant {tenant_label}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert own_marker in result.stdout, (
        f"tenant {tenant_label} search did not return its own seeded "
        f"marker ({own_marker!r}); fixture-seed may have failed or "
        f"D24 predicate over-filtered. stdout={result.stdout!r}"
    )
    assert other_marker not in result.stdout, (
        f"tenant {tenant_label} search leaked the OTHER tenant's "
        f"marker ({other_marker!r}); D24 tenant predicate violated. "
        f"stdout={result.stdout!r}"
    )


@pytest.mark.parametrize("tenant_label", ["a", "b"])
def test_traverse_against_tenant_with_no_seeded_entity_returns_no_results(
    red_team_state: None, tenant_label: str
) -> None:
    """The fixture seeds Postgres chunks only, not Neo4j graph nodes;
    querying the traverse path for an entity that exists in neither
    tenant's subgraph returns (no results). Paired with the search
    cross-tenant non-leak test above, the application-level retrieval
    surface is exercised across both retrieval paths.

    Per D63 (property-based Neo4j scoping), the cross-tenant graph-
    read isolation contract lives at test_neo4j_isolation.py; this
    test asserts only that the application-layer traverse honours
    the predicate when no matching entity exists.
    """
    result = _exec_in_api(
        "python", "-m", "apps.cli", "ingest", "traverse",
        "AnyEntityThatDoesNotExist",
        "--tenant-id", tenant_label, "--depth", "1",
    )
    assert result.returncode == 0, (
        f"ingest traverse failed for tenant {tenant_label}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "(no results)" in result.stdout, (
        f"tenant {tenant_label} traverse unexpectedly returned: "
        f"{result.stdout!r}"
    )
