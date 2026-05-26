"""Tenant isolation contract test for the intent-classification evaluation substrate (D137).

Per D32, per-tenant data planes are independent Postgres instances.
Per D137, the three runner-substrate tables
(``intent_class_evaluation_runs``,
``intent_class_evaluation_results``,
``intent_class_evaluation_aggregates``) live on each tenant's
database, NOT on the control plane.

Two layers, mirroring the P11 ``test_evaluation_run_isolation.py``
precedent:

1. Structural isolation: each tenant's DB carries the three tables
   from migration 0022; the control-plane DB does not.

2. Behavioural cross-tenant isolation: the bound-tenant defence-in-
   depth ValueError fires when a TenantContext or EvaluationRun
   carries a tenant_id that does not match the adapter's bound
   tenant.

Synthetic fixture provisions a UUID per tenant; the bound-tenant
assertion fires at adapter construction time without requiring a
live DB connection.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone

import pytest

from contexts.intent_classification_evaluation.adapters.outbound.postgres.repository import (
    PostgresEvaluationRunRepository,
)
from contexts.intent_classification_evaluation.domain.evaluation_run import (
    EvaluationRun,
    EvaluationRunStatus,
)
from shared_kernel import TenantContext, TenantId
from shared_kernel.inference import (
    DEFAULT_ACCOUNT,
    LatencyTier,
    ModelConfiguration,
    ModelIdentifier,
    Provider,
)


# --- Structural isolation (docker compose exec psql) ---


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


_EXPECTED_TABLES = (
    "intent_class_evaluation_runs",
    "intent_class_evaluation_results",
    "intent_class_evaluation_aggregates",
)


@pytest.mark.parametrize(
    "service,user_env,db_env",
    [
        ("postgres-tenant-a", "POSTGRES_TENANT_A_USER", "POSTGRES_TENANT_A_DB"),
        ("postgres-tenant-b", "POSTGRES_TENANT_B_USER", "POSTGRES_TENANT_B_DB"),
    ],
)
def test_per_tenant_db_carries_the_three_eval_tables(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """Positive case: per-tenant DB carries all three substrate tables."""
    user = _env(user_env)
    db = _env(db_env)
    quoted = ", ".join(f"'{t}'" for t in _EXPECTED_TABLES)
    found = _exec_psql(
        service,
        user,
        db,
        (
            "SELECT table_name FROM information_schema.tables "
            f"WHERE table_name IN ({quoted}) "
            "ORDER BY table_name"
        ),
    )
    found_set = set(found.splitlines())
    assert found_set == set(_EXPECTED_TABLES), (
        f"per-tenant DB {service} missing one or more tables; found {found_set}"
    )


def test_control_plane_db_has_no_eval_tables(
    compose_running: None,
) -> None:
    """Negative case: the control-plane DB does NOT carry the substrate tables."""
    user = _env("POSTGRES_CONTROL_PLANE_USER")
    db = _env("POSTGRES_CONTROL_PLANE_DB")
    quoted = ", ".join(f"'{t}'" for t in _EXPECTED_TABLES)
    found = _exec_psql(
        "postgres-control-plane",
        user,
        db,
        (
            "SELECT count(*) FROM information_schema.tables "
            f"WHERE table_name IN ({quoted})"
        ),
    )
    assert found == "0", (
        f"control-plane DB should have none of the per-tenant eval "
        f"tables; information_schema reported {found}"
    )


# --- Behavioural isolation (bound-tenant defence-in-depth ValueError) ---


def _model_identifier() -> ModelIdentifier:
    return ModelIdentifier(
        provider=Provider.OPENAI,
        account=DEFAULT_ACCOUNT,
        version="gpt-4o-mini",
        configuration=ModelConfiguration(
            latency_tier=LatencyTier.REAL_TIME_REQUIRED,
            temperature=0.0,
            max_tokens=None,
            structured_output_schema=None,
        ),
    )


def _tenant_context(tenant_uuid: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_uuid,
        jurisdiction="us-east-1",
        cost_attribution_id=tenant_uuid,
    )


def _evaluation_run(*, tenant_uuid: str) -> EvaluationRun:
    return EvaluationRun(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(tenant_uuid),
        gold_set_name="phase_2_a_default",
        model_identifier=_model_identifier(),
        status=EvaluationRunStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
        completed_at=None,
        failure_reason=None,
    )


async def _no_resolver(_tid):  # pragma: no cover — exercised only on negative paths
    raise AssertionError(
        "session resolver invoked despite bound-tenant ValueError gate"
    )


def test_bound_tenant_mismatch_on_tenant_context_blocks_create() -> None:
    """The repository raises ValueError when TenantContext mismatches bound tenant."""
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    repo = PostgresEvaluationRunRepository(
        per_tenant_sessionmaker_resolver=_no_resolver,
        bound_tenant_id=TenantId(tenant_a),
    )
    other_tenant = _tenant_context(tenant_b)
    other_run = _evaluation_run(tenant_uuid=tenant_b)

    import asyncio

    with pytest.raises(ValueError, match="bound tenant"):
        asyncio.run(repo.create_run(other_run, tenant=other_tenant))


def test_bound_tenant_mismatch_on_run_tenant_id_blocks_create() -> None:
    """The repository raises ValueError when EvaluationRun.tenant_id mismatches bound tenant.

    Defence-in-depth: even when TenantContext matches the bound
    tenant, an EvaluationRun whose tenant_id differs (programmer
    error path) gets rejected.
    """
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    repo = PostgresEvaluationRunRepository(
        per_tenant_sessionmaker_resolver=_no_resolver,
        bound_tenant_id=TenantId(tenant_a),
    )
    matching_tenant = _tenant_context(tenant_a)
    wrong_run = _evaluation_run(tenant_uuid=tenant_b)

    import asyncio

    with pytest.raises(ValueError, match="bound tenant"):
        asyncio.run(repo.create_run(wrong_run, tenant=matching_tenant))


def test_bound_tenant_match_passes_into_session_call() -> None:
    """When both sides match, the resolver is called (no early ValueError).

    Asserts the negative-path is the only blocking branch — a matching
    pair gets through to the session resolver. Uses a sentinel resolver
    that raises a distinct exception so the test can confirm the gate
    let the call through.
    """
    tenant_a = str(uuid.uuid4())
    matching_tenant = _tenant_context(tenant_a)
    matching_run = _evaluation_run(tenant_uuid=tenant_a)

    class _Sentinel(Exception):
        pass

    async def _sentinel_resolver(_tid):
        raise _Sentinel("resolver reached")

    repo = PostgresEvaluationRunRepository(
        per_tenant_sessionmaker_resolver=_sentinel_resolver,
        bound_tenant_id=TenantId(tenant_a),
    )

    import asyncio

    with pytest.raises(_Sentinel, match="resolver reached"):
        asyncio.run(repo.create_run(matching_run, tenant=matching_tenant))
