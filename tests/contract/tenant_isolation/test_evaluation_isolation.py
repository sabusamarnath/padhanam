"""Tenant isolation contract test for the evaluation tables (D32).

Per D32, per-tenant data planes are independent Postgres instances;
control-plane carries operator-owned, jurisdiction-spanning data only.
The seven evaluation tables (D53) live on the per-tenant track and
must exist on each tenant's database; the control-plane database must
not have them.

Asserts the structural invariant directly against running DBs by
shelling out to ``docker compose exec`` and querying
``information_schema.tables`` on each instance. Skips cleanly when
the Compose stack is not reachable, matching the cost-columns and
audit-isolation precedents.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest


_EVALUATION_TABLES = (
    "scoring_sheets",
    "scoring_sheet_revisions",
    "scoring_sheet_criteria",
    "appliers",
    "interaction_sets",
    "interactions",
    "rubric_applications",
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
    in_clause = ", ".join(f"'{t}'" for t in _EVALUATION_TABLES)
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
def test_per_tenant_db_has_all_seven_evaluation_tables(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """Positive case for D32 per-tenant track: each tenant's DB
    carries the seven evaluation tables.
    """
    user = _env(user_env)
    db = _env(db_env)
    found = set(
        _exec_psql(service, user, db, _table_list_query()).splitlines()
    )
    assert found == set(_EVALUATION_TABLES), (
        f"per-tenant DB {service} missing one or more evaluation tables; "
        f"found {sorted(found)}"
    )


def test_control_plane_db_has_no_evaluation_tables(
    compose_running: None,
) -> None:
    """Negative case for D32 instance independence: control-plane DB
    has none of the seven evaluation tables. Per-tenant data must not
    leak onto the control plane.
    """
    user = _env("POSTGRES_CONTROL_PLANE_USER")
    db = _env("POSTGRES_CONTROL_PLANE_DB")
    found = _exec_psql(
        "postgres-control-plane", user, db, _table_list_query()
    )
    assert found == "", (
        f"control-plane should have no evaluation tables; psql reported "
        f"{found!r}"
    )
