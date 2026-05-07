"""Concurrent-workers test for the SKIP LOCKED claim semantics (D60).

Two worker processes run concurrently against tenant_a; a single
source is registered. Exactly one worker must claim it; the other
must report 0 sources processed. The contract under test is that
``SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`` plus the in-
transaction state transition prevents two workers from racing on
the same row.

This is the worker-loop counterpart of the structural tenant-
isolation contract test: that one verifies the schema-level
isolation; this one verifies the runtime-level concurrency
isolation. Together they cover the "is the SKIP LOCKED pattern
honest under load" question the brief's reflection prompt 2 asks.

Skips cleanly when Compose is not reachable.
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
import threading
import time
from typing import Tuple

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
    needed = {"padhanam-api", "postgres-tenant-a"}
    if not needed.issubset(running):
        missing = needed - running
        pytest.skip(f"compose services not running: {sorted(missing)}")


def _exec_psql_tenant_a(query: str) -> str:
    cmd = (
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "' +
        query.replace('"', '\\"') + '"'
    )
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres-tenant-a",
            "sh",
            "-c",
            cmd,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return result.stdout.strip()


def _write_file(path: str, content: str) -> None:
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
    proc.communicate(input=content.encode("utf-8"), timeout=10)


def _ingest_run(file_path: str) -> str:
    result = subprocess.run(
        [
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
            "a",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return result.stdout.strip().splitlines()[-1]


def _run_worker_thread(out: list[Tuple[int, str]], idx: int) -> None:
    """Run a single bounded-iteration worker invocation; record
    (exit_code, stdout) into the shared list at the given index.
    """
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "padhanam-api",
            "python",
            "-m",
            "apps.cli",
            "ingest",
            "worker",
            "--tenant-id",
            "a",
            "--max-iterations",
            "3",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    out[idx] = (result.returncode, result.stdout)


def test_two_concurrent_workers_claim_one_source_each(
    compose_running: None,
) -> None:
    """Single source registered; two workers race; total processed
    across both = 1. SKIP LOCKED ensures no double-processing.
    """
    _exec_psql_tenant_a("TRUNCATE TABLE chunks, sources;")
    _write_file(
        "/tmp/e2e_concurrency.md",
        textwrap.dedent(
            """\
            # Race
            One source, two workers, one winner.
            """
        ),
    )
    _ingest_run("/tmp/e2e_concurrency.md")

    out: list[Tuple[int, str]] = [(0, ""), (0, "")]
    t1 = threading.Thread(target=_run_worker_thread, args=(out, 0))
    t2 = threading.Thread(target=_run_worker_thread, args=(out, 1))
    t1.start()
    # Tiny stagger so the second claim attempt actually races the
    # first one's lock; without it the threads can serialise on the
    # docker-compose-exec startup cost. The SKIP LOCKED contract
    # holds either way, but the staggered start exercises the lock
    # contention path explicitly.
    time.sleep(0.05)
    t2.start()
    t1.join(timeout=90)
    t2.join(timeout=90)

    # Both invocations completed cleanly.
    assert out[0][0] == 0, f"worker 1 stdout={out[0][1]!r}"
    assert out[1][0] == 0, f"worker 2 stdout={out[1][1]!r}"

    processed_each = []
    for code, stdout in out:
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("worker: processed "):
                # "worker: processed N source(s)"
                count = int(line.split()[2])
                processed_each.append(count)
                break
    assert len(processed_each) == 2
    # Exactly one worker claimed the row; the other claimed nothing.
    assert sorted(processed_each) == [0, 1], processed_each

    # Source ended up parsed exactly once with one chunk row.
    state = _exec_psql_tenant_a("SELECT state FROM sources")
    assert state == "parsed"
    chunk_count = _exec_psql_tenant_a("SELECT count(*) FROM chunks")
    assert chunk_count == "1"
