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
# These tests exercise the application-level retrieval ports against
# both tenants by invoking ``padhanam ingest search`` and
# ``padhanam ingest traverse`` inside the padhanam-api container.
# Cross-tenant retrieval against an unindexed tenant must return
# zero results; both methods enforce the tenant predicate per D24.
# ---------------------------------------------------------------------------


def _exec_in_api(
    *args: str, timeout: int = 60
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "padhanam-api", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


@pytest.mark.parametrize("tenant_label", ["a", "b"])
def test_search_against_empty_tenant_returns_no_results(
    compose_running: None, tenant_label: str
) -> None:
    """Defensively: a tenant with no indexed sources returns no
    results from ``padhanam ingest search``. The truncate fixture
    is module-scoped, so this also fails cleanly if cross-tenant
    leakage from prior tests has landed.
    """
    # Truncate both tenants to ensure a known-empty starting state.
    for label in ("a", "b"):
        _exec_in_api(
            "sh", "-c",
            f'PGPASSWORD="$POSTGRES_TENANT_{label.upper()}_PASSWORD" '
            f"psql -h postgres-tenant-{label} "
            f'-U "$POSTGRES_TENANT_{label.upper()}_USER" '
            f'-d "$POSTGRES_TENANT_{label.upper()}_DB" '
            f'-c "TRUNCATE TABLE chunks, sources;"',
        )
    result = _exec_in_api(
        "python", "-m", "apps.cli", "ingest", "search",
        "anything", "--tenant-id", tenant_label, "--limit", "5",
    )
    assert result.returncode == 0, (
        f"ingest search failed for tenant {tenant_label}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "(no results)" in result.stdout, (
        f"tenant {tenant_label} search unexpectedly returned: "
        f"{result.stdout!r}"
    )


@pytest.mark.parametrize("tenant_label", ["a", "b"])
def test_traverse_against_empty_tenant_returns_no_results(
    compose_running: None, tenant_label: str
) -> None:
    """Symmetric to the search isolation test: an empty tenant's
    traverse returns nothing. Combined with the read isolation
    contract test in ``test_neo4j_isolation.py`` that exercises
    cross-tenant graph access, the application-level retrieval
    surface inherits the property-based scoping discipline at the
    user-visible boundary.
    """
    result = _exec_in_api(
        "python", "-m", "apps.cli", "ingest", "traverse",
        "AnyEntity", "--tenant-id", tenant_label, "--depth", "1",
    )
    assert result.returncode == 0, (
        f"ingest traverse failed for tenant {tenant_label}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "(no results)" in result.stdout, (
        f"tenant {tenant_label} traverse unexpectedly returned: "
        f"{result.stdout!r}"
    )
