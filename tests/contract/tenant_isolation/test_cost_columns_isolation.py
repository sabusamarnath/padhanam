"""Tenant isolation contract test for the cost-attribution and
cost-ceiling columns landed at S14 (D32 instance independence).

D41 commits the cost-attribution column to the control-plane tenant
registry. D32 commits per-tenant Postgres instance independence: each
tenant's data plane has its own database with no shared schema across
tenants. The per-tenant Alembic track does not run the control-plane's
``0003_add_cost_columns`` revision because per-tenant DBs do not have
the ``tenant_registry`` table at all (the registry is a control-plane-
only concept).

This test asserts that structural invariant directly against running
DBs by shelling out to ``docker compose exec`` and querying
``information_schema.tables`` on each per-tenant Postgres instance.
The control-plane DB is also queried as the positive case so the test
fails loudly if both halves break (the negative-case-only assertion
would miss the case where the control-plane lost the table too).

Skips cleanly when the Compose stack is not reachable (e.g. running
``uv run pytest`` on a host without the dev stack up). The skip is
honest: this test is a contract over a specific runtime topology, and
it cannot be evaluated when the topology is absent.
"""
from __future__ import annotations

import os
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


def _exec_psql(service: str, user: str, db: str, query: str) -> str:
    """Run ``psql -tAc <query>`` inside ``service``. Returns stdout
    stripped of trailing whitespace. Surfaces non-zero exits as
    test-time errors so the assertion site sees the real shell output.
    """
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
    # Confirm the three Postgres services are up; otherwise the queries
    # below will fail with confusing errors.
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
    """Read an env var from the host's .env file via os.environ.

    The dev stack populates these via the Make targets that source
    .env; tests that run after ``make migrate`` inherit them. If a
    value is missing, fall back to reading .env directly so the test
    runs cleanly under a bare ``uv run pytest`` invocation.
    """
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


def test_control_plane_tenant_registry_has_cost_columns(
    compose_running: None,
) -> None:
    """Positive case: the control-plane DB carries the three new
    columns introduced by Alembic revision 0003_add_cost_columns.
    """
    user = _env("POSTGRES_CONTROL_PLANE_USER")
    db = _env("POSTGRES_CONTROL_PLANE_DB")
    columns = _exec_psql(
        "postgres-control-plane",
        user,
        db,
        (
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'tenant_registry' "
            "AND column_name IN ("
            "'cost_attribution_id', 'cost_ceiling_usd_monthly', "
            "'cost_ceiling_action') "
            "ORDER BY column_name"
        ),
    )
    found = set(columns.splitlines())
    assert found == {
        "cost_attribution_id",
        "cost_ceiling_action",
        "cost_ceiling_usd_monthly",
    }, f"control-plane missing one or more cost columns; found {found}"


@pytest.mark.parametrize(
    "service,user_env,db_env",
    [
        ("postgres-tenant-a", "POSTGRES_TENANT_A_USER", "POSTGRES_TENANT_A_DB"),
        ("postgres-tenant-b", "POSTGRES_TENANT_B_USER", "POSTGRES_TENANT_B_DB"),
    ],
)
def test_per_tenant_db_has_no_tenant_registry_table(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """Negative case for D32 instance independence: per-tenant DBs do
    not have the ``tenant_registry`` table at all, so the cost columns
    cannot exist on them. The structural invariant is the absence of
    the parent table, not just the absence of the columns.
    """
    user = _env(user_env)
    db = _env(db_env)
    table_count = _exec_psql(
        service,
        user,
        db,
        (
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name = 'tenant_registry'"
        ),
    )
    assert table_count == "0", (
        f"per-tenant DB {service} should have no tenant_registry table; "
        f"information_schema reported {table_count}"
    )
