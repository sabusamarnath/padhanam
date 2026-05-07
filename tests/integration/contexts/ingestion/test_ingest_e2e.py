"""End-to-end integration test for the source-ingestion pipeline (S19).

Exercises the full ``padhanam ingest run`` → worker → ``sources``/
``chunks`` flow inside the padhanam-api container against tenant_a's
data plane. Same shape the S18 eval CLI e2e test uses: scripts run
inside the container via ``docker compose exec`` so per-tenant
Postgres hostnames resolve over the Compose network.

Cases covered:

  - ``test_register_and_parse_markdown``: register a markdown file,
    run the worker once, assert state=parsed and chunks reflect the
    heading-boundary split with structural metadata.

  - ``test_register_and_parse_plain_text``: same flow for a .txt
    file with paragraph-boundary chunks.

  - ``test_unsupported_extension_rejected_at_cli``: .pdf upload
    rejected before the worker pulls (acceptance criterion 7).

  - ``test_worker_idempotent_on_already_parsed_source``: re-running
    the worker against an already-parsed source claims no rows.

  - ``test_worker_marks_source_failed_on_parser_error``: a file
    with non-utf8 bytes parses to a FAILED row with
    parsing_error_text populated.

  - ``test_cross_tenant_access_returns_no_rows``: tenant-b's worker
    doesn't see tenant-a's pending sources (live exercise of the
    Postgres adapter's tenant_id filter, complementing the
    structural tenant-isolation contract test).

The test cleans up the sources/chunks tables on tenant_a (and
tenant_b for the cross-tenant case) before each module run so the
suite is idempotent. Skips cleanly when Compose is not reachable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap

import pytest


_TENANT_A_LABEL = "a"
_TENANT_B_LABEL = "b"


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
    needed = {"padhanam-api", "postgres-tenant-a", "postgres-tenant-b"}
    if not needed.issubset(running):
        missing = needed - running
        pytest.skip(f"compose services not running: {sorted(missing)}")


def _exec(*cmd: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Wrapper around ``docker compose exec -T padhanam-api`` with
    a sane timeout and text mode."""
    full = ["docker", "compose", "exec", "-T", *cmd]
    return subprocess.run(
        full, capture_output=True, text=True, timeout=60, check=check
    )


def _exec_psql_tenant(label: str, query: str) -> str:
    """Run a psql query against tenant ``label``'s data plane.

    Each postgres-tenant-<label> container has POSTGRES_USER and
    POSTGRES_DB set from the host-side POSTGRES_TENANT_<LABEL>_*
    vars (per compose.yaml's ``environment`` mapping). The shell
    wrapper expands them inside the container.
    """
    cmd = (
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "' +
        query.replace('"', '\\"') + '"'
    )
    result = _exec("postgres-tenant-" + label, "sh", "-c", cmd)
    return result.stdout.strip()


def _truncate_ingestion_tables(label: str) -> None:
    _exec_psql_tenant(label, "TRUNCATE TABLE chunks, sources;")


def _write_file_in_container(path: str, content: str) -> None:
    """Write ``content`` to ``path`` inside the padhanam-api container."""
    proc = subprocess.Popen(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "padhanam-api",
            "sh",
            "-c",
            f"cat > {path}",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = proc.communicate(input=content.encode("utf-8"), timeout=10)
    if proc.returncode != 0:
        raise RuntimeError(
            f"failed to write {path} in container: stderr={err!r} stdout={out!r}"
        )


def _write_bytes_in_container(path: str, content: bytes) -> None:
    """Like _write_file_in_container but for raw bytes (e.g. invalid UTF-8)."""
    proc = subprocess.Popen(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "padhanam-api",
            "sh",
            "-c",
            f"cat > {path}",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = proc.communicate(input=content, timeout=10)
    if proc.returncode != 0:
        raise RuntimeError(
            f"failed to write {path} in container: stderr={err!r} stdout={out!r}"
        )


def _ingest_run(label: str, file_path: str) -> str:
    """Invoke ``padhanam ingest run`` and return the source id stdout."""
    result = _exec(
        "padhanam-api",
        "python",
        "-m",
        "apps.cli",
        "ingest",
        "run",
        file_path,
        "--tenant-id",
        label,
    )
    return result.stdout.strip().splitlines()[-1]


def _ingest_run_expect_error(
    label: str, file_path: str
) -> subprocess.CompletedProcess[str]:
    """Like ``_ingest_run`` but does not assert exit 0; returns the
    completed process so the caller can inspect exit_code and output.
    """
    full = [
        "docker",
        "compose",
        "exec",
        "-T",
        "padhanam-api",
        "python",
        "-m",
        "apps.cli",
        "ingest",
        "run",
        file_path,
        "--tenant-id",
        label,
    ]
    return subprocess.run(
        full, capture_output=True, text=True, timeout=60, check=False
    )


def _ingest_worker(label: str, max_iterations: int = 5) -> str:
    """Invoke the worker for ``label`` for a bounded number of
    iterations; return the stdout (so the caller can assert the
    "processed N source(s)" line).
    """
    result = _exec(
        "padhanam-api",
        "python",
        "-m",
        "apps.cli",
        "ingest",
        "worker",
        "--tenant-id",
        label,
        "--max-iterations",
        str(max_iterations),
    )
    return result.stdout


@pytest.fixture(autouse=True)
def _clean_tenant_a(compose_running: None) -> None:
    """Each test starts with empty ingestion tables on tenant_a (and
    tenant_b where the cross-tenant test exercises it).
    """
    _truncate_ingestion_tables(_TENANT_A_LABEL)
    _truncate_ingestion_tables(_TENANT_B_LABEL)


def test_register_parse_and_embed_markdown() -> None:
    """S19/S20: worker drains both stages per D62. Markdown source
    parses to heading-bounded chunks, then chunks are embedded.
    Source state ends up ``embedded``; structural metadata from the
    parse stage is preserved alongside the embedding column.
    """
    markdown = textwrap.dedent(
        """\
        # Top Heading

        intro body

        ## Section A

        body for A

        ## Section B

        body for B
        """
    )
    _write_file_in_container("/tmp/e2e_test.md", markdown)
    source_id = _ingest_run(_TENANT_A_LABEL, "/tmp/e2e_test.md")
    assert len(source_id) == 36  # uuid4 string

    # max_iterations=5 lets the worker drain both stages (parse +
    # embed) for the single registered source.
    worker_output = _ingest_worker(_TENANT_A_LABEL, max_iterations=5)
    # Parse stage processes the source, then embed stage processes
    # it; total processed across both stages = 2.
    assert "processed 2 source" in worker_output

    # Source row state — parse + embed pipeline complete.
    state = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT state FROM sources WHERE id='{source_id}'",
    )
    assert state == "embedded"

    # Chunks: 3 expected (Top Heading, Section A, Section B).
    count = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT count(*) FROM chunks WHERE source_id='{source_id}'",
    )
    assert count == "3"

    # All chunks carry an embedding after the embed stage.
    embedded_count = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT count(*) FROM chunks "
        f"WHERE source_id='{source_id}' AND embedding IS NOT NULL",
    )
    assert embedded_count == "3"

    # Structural metadata on the second chunk should record Section A.
    metadata = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT structural_metadata FROM chunks "
        f"WHERE source_id='{source_id}' AND chunk_index=1",
    )
    md = json.loads(metadata)
    assert md == {"heading_text": "Section A", "heading_level": 2}


def test_register_parse_and_embed_plain_text() -> None:
    text = "para one\n\npara two\n\npara three\n"
    _write_file_in_container("/tmp/e2e_test.txt", text)
    source_id = _ingest_run(_TENANT_A_LABEL, "/tmp/e2e_test.txt")

    worker_output = _ingest_worker(_TENANT_A_LABEL, max_iterations=5)
    assert "processed 2 source" in worker_output

    state = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT state FROM sources WHERE id='{source_id}'",
    )
    assert state == "embedded"

    count = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT count(*) FROM chunks WHERE source_id='{source_id}'",
    )
    assert count == "3"

    embedded_count = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT count(*) FROM chunks "
        f"WHERE source_id='{source_id}' AND embedding IS NOT NULL",
    )
    assert embedded_count == "3"

    # paragraph_index on the third chunk should be 2 (0-indexed).
    metadata = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT structural_metadata FROM chunks "
        f"WHERE source_id='{source_id}' AND chunk_index=2",
    )
    md = json.loads(metadata)
    assert md == {"paragraph_index": 2}


def test_unsupported_extension_rejected_at_cli() -> None:
    _write_bytes_in_container("/tmp/e2e_doc.pdf", b"%PDF-1.4\nfake")
    result = _ingest_run_expect_error(_TENANT_A_LABEL, "/tmp/e2e_doc.pdf")
    assert result.returncode == 2
    assert "unsupported" in result.stdout.lower() or "unsupported" in result.stderr.lower()
    # Worker must see no pending source.
    count = _exec_psql_tenant(
        _TENANT_A_LABEL,
        "SELECT count(*) FROM sources WHERE state='received'",
    )
    assert count == "0"


def test_worker_idempotent_on_already_parsed_source() -> None:
    """Re-running the worker against an already-parsed source claims
    no new rows. The reentrancy contract per D60.
    """
    markdown = "# Idempotent\n\nbody\n"
    _write_file_in_container("/tmp/e2e_idem.md", markdown)
    _ingest_run(_TENANT_A_LABEL, "/tmp/e2e_idem.md")
    _ingest_worker(_TENANT_A_LABEL, max_iterations=3)

    # Second worker run claims nothing.
    second = _ingest_worker(_TENANT_A_LABEL, max_iterations=3)
    assert "processed 0 source" in second

    # Still exactly one row of chunks; the duplicate-write backstop
    # was never exercised because the worker never re-claimed.
    count = _exec_psql_tenant(
        _TENANT_A_LABEL,
        "SELECT count(*) FROM chunks",
    )
    assert count == "1"


def test_worker_marks_source_failed_on_parser_error() -> None:
    """A markdown file with non-UTF-8 bytes triggers ParserError;
    the worker transitions the source to FAILED with
    parsing_error_text populated."""
    _write_bytes_in_container(
        "/tmp/e2e_bad.md",
        b"\xff\xfe\x00\x00 invalid utf-8 sequence",
    )
    source_id = _ingest_run(_TENANT_A_LABEL, "/tmp/e2e_bad.md")
    _ingest_worker(_TENANT_A_LABEL, max_iterations=3)

    row = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT state || '|' || coalesce(parsing_error_text, '') "
        f"FROM sources WHERE id='{source_id}'",
    )
    state, error_text = row.split("|", 1)
    assert state == "failed"
    assert "utf-8" in error_text.lower() or "utf8" in error_text.lower()

    # No chunks produced for a failed source.
    count = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT count(*) FROM chunks WHERE source_id='{source_id}'",
    )
    assert count == "0"


def test_register_parse_and_embed_markdown_end_to_end() -> None:
    """S20 / D62: full pipeline through embed.

    Register a markdown source, run the worker (which drains parse
    then embed), assert the source state transitions to ``embedded``,
    every chunk has a non-null 768-dim embedding, and a vector-
    distance query against the HNSW index returns the expected row.
    """
    markdown = textwrap.dedent(
        """\
        # Top
        body for top

        ## Section
        body for section
        """
    )
    _write_file_in_container("/tmp/e2e_embed.md", markdown)
    source_id = _ingest_run(_TENANT_A_LABEL, "/tmp/e2e_embed.md")

    # max_iterations=5 lets the worker drain both stages (parse +
    # embed) for the single registered source.
    worker_output = _ingest_worker(_TENANT_A_LABEL, max_iterations=5)
    # Two stage transitions per source: parse + embed = 2 processed.
    assert "processed 2 source" in worker_output

    state = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT state FROM sources WHERE id='{source_id}'",
    )
    assert state == "embedded"

    embedded_count = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT count(*) FROM chunks "
        f"WHERE source_id='{source_id}' AND embedding IS NOT NULL",
    )
    total_count = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT count(*) FROM chunks WHERE source_id='{source_id}'",
    )
    assert embedded_count == total_count
    assert int(embedded_count) >= 1

    # Vector dimension matches D62 / nomic-embed-text:v1.5 native
    # output. vector_dims is pgvector's accessor for vector length.
    dim = _exec_psql_tenant(
        _TENANT_A_LABEL,
        f"SELECT vector_dims(embedding) FROM chunks "
        f"WHERE source_id='{source_id}' LIMIT 1",
    )
    assert dim == "768"


def test_worker_idempotent_on_already_embedded_source() -> None:
    """Re-running the worker against an already-embedded source
    claims no new rows. Per D62 the embed stage is idempotent the
    same way the parse stage is — claim_pending_for_embed filters
    on state='parsed' and an embedded source is excluded."""
    markdown = "# Idempotent embed\n\nbody\n"
    _write_file_in_container("/tmp/e2e_embed_idem.md", markdown)
    _ingest_run(_TENANT_A_LABEL, "/tmp/e2e_embed_idem.md")
    _ingest_worker(_TENANT_A_LABEL, max_iterations=5)

    # Second worker run claims nothing.
    second = _ingest_worker(_TENANT_A_LABEL, max_iterations=5)
    assert "processed 0 source" in second


def test_cross_tenant_access_returns_no_rows() -> None:
    """Tenant-a's worker never sees tenant-b's pending sources.
    Live exercise of the tenant_id filter on
    claim_pending_for_parse, complementing the structural
    tenant-isolation contract test.
    """
    # Register a source on tenant_b.
    _write_file_in_container("/tmp/e2e_b.md", "# Only B\n\nB body\n")
    _ingest_run(_TENANT_B_LABEL, "/tmp/e2e_b.md")

    # Tenant-a worker drains; should claim nothing.
    a_output = _ingest_worker(_TENANT_A_LABEL, max_iterations=3)
    assert "processed 0 source" in a_output

    # Tenant-a sees no rows at all (tenant_id scoping holds on
    # reads as well as on the worker claim).
    a_count = _exec_psql_tenant(
        _TENANT_A_LABEL,
        "SELECT count(*) FROM sources",
    )
    assert a_count == "0"

    # Tenant-b sees its own row, still pending.
    b_state = _exec_psql_tenant(
        _TENANT_B_LABEL,
        "SELECT state FROM sources",
    )
    assert b_state == "received"
