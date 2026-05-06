"""End-to-end integration test for the evaluation harness foundations.

Drives the full apply_scoring_sheet use case through:
- a real per-tenant Postgres database (tenant-a's data plane);
- the PostgresScoringSheetRepository read path;
- the PolymorphicApplier dispatching to the deterministic library;
- the PostgresRubricApplicationRepository write path.

The seeded tenants live on Compose-internal-only Postgres instances so
the scenario runs *inside* the padhanam-api container via
``docker compose exec`` — same pattern test_p3_full_slice and
test_s15_tenant_context_e2e use.

Skips cleanly when Compose is not reachable, matching the S14
precedent. Idempotent: each run cleans the evaluation tables on
tenant-a before inserting fresh fixture rows, so re-runs do not
accumulate test data.
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


_E2E_SCRIPT = """
import asyncio
import json
import sys
from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from contexts.evaluation.adapters.outbound.polymorphic_applier import (
    PolymorphicApplier,
)
from contexts.evaluation.adapters.outbound.postgres._tables import (
    appliers,
    interaction_sets,
    interactions,
    rubric_applications,
    scoring_sheet_criteria,
    scoring_sheet_revisions,
    scoring_sheets,
)
from contexts.evaluation.adapters.outbound.postgres.rubric_application_repository import (
    PostgresRubricApplicationRepository,
)
from contexts.evaluation.adapters.outbound.postgres.scoring_sheet_repository import (
    PostgresScoringSheetRepository,
)
from contexts.evaluation.application.apply_scoring_sheet import (
    apply_scoring_sheet,
)
from contexts.evaluation.domain.interaction import Interaction
from padhanam.config import TenantPostgresSettings
from shared_kernel import TenantContext


TENANT_A_UUID = "00000000-0000-4000-8000-00000000a001"


def _async_url(s: TenantPostgresSettings) -> str:
    return f"postgresql+asyncpg://{s.user}:{s.password}@{s.host}:{s.port}/{s.db}"


async def _truncate(session_factory) -> None:
    async with session_factory() as session:
        # FK order matters: child rows first.
        for table in (
            rubric_applications,
            interactions,
            interaction_sets,
            appliers,
            scoring_sheet_criteria,
            scoring_sheet_revisions,
            scoring_sheets,
        ):
            await session.execute(sa.delete(table))
        await session.commit()


async def _insert_fixtures(session_factory):
    sheet_id = uuid4()
    revision_id = uuid4()
    criterion_id = uuid4()
    applier_id = uuid4()
    interaction_set_id = uuid4()
    interaction_id = uuid4()
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        await session.execute(
            sa.insert(scoring_sheets).values(
                id=str(sheet_id),
                name="S16 e2e sheet",
                description="End-to-end harness test sheet",
                created_by_user_id="system:test:s16",
                created_at=now,
                archived_at=None,
            )
        )
        await session.execute(
            sa.insert(scoring_sheet_revisions).values(
                id=str(revision_id),
                scoring_sheet_id=str(sheet_id),
                version=1,
                description="initial revision",
                created_by_user_id="system:test:s16",
                created_at=now,
            )
        )
        await session.execute(
            sa.insert(scoring_sheet_criteria).values(
                id=str(criterion_id),
                scoring_sheet_revision_id=str(revision_id),
                name="exact match",
                description="output exactly equals expected_output['value']",
                levels=[
                    {
                        "label": "pass",
                        "definition": "exact match",
                        "is_success": True,
                    },
                    {
                        "label": "fail",
                        "definition": "not exact match",
                        "is_success": False,
                    },
                ],
                ordering=0,
            )
        )
        await session.execute(
            sa.insert(appliers).values(
                id=str(applier_id),
                scoring_sheet_revision_id=str(revision_id),
                criterion_id=str(criterion_id),
                applier_type="deterministic",
                deterministic_function_name="exact_match",
                prompt_template=None,
                judge_model=None,
            )
        )
        await session.execute(
            sa.insert(interaction_sets).values(
                id=str(interaction_set_id),
                name="S16 e2e set",
                description=None,
                created_by_user_id="system:test:s16",
                created_at=now,
            )
        )
        await session.execute(
            sa.insert(interactions).values(
                id=str(interaction_id),
                interaction_set_id=str(interaction_set_id),
                input={"prompt": "say hello"},
                expected_output={"value": "hello"},
                ordering=0,
                created_at=now,
            )
        )
        await session.commit()
    return revision_id, interaction_id, interaction_set_id, criterion_id, applier_id, now


async def _run() -> dict:
    a = TenantPostgresSettings.for_tenant("a")
    b = TenantPostgresSettings.for_tenant("b")
    a_engine = create_async_engine(_async_url(a))
    a_factory = async_sessionmaker(a_engine, expire_on_commit=False)
    b_engine = create_async_engine(_async_url(b))
    b_factory = async_sessionmaker(b_engine, expire_on_commit=False)

    try:
        # Fresh slate on tenant-a; tenant-b is untouched throughout.
        await _truncate(a_factory)
        (
            revision_id,
            interaction_id,
            interaction_set_id,
            criterion_id,
            applier_id,
            now,
        ) = await _insert_fixtures(a_factory)

        sheet_repo = PostgresScoringSheetRepository(a_factory)
        rubric_repo = PostgresRubricApplicationRepository(a_factory)
        applier = PolymorphicApplier()
        tenant_context = TenantContext(
            tenant_id=TENANT_A_UUID,
            jurisdiction="eu-west",
            cost_attribution_id=TENANT_A_UUID,
        )
        interaction = Interaction(
            id=interaction_id,
            interaction_set_id=interaction_set_id,
            input={"prompt": "say hello"},
            expected_output={"value": "hello"},
            ordering=0,
            created_at=now,
        )

        first = await apply_scoring_sheet(
            tenant_context=tenant_context,
            scoring_sheet_revision_id=revision_id,
            interaction=interaction,
            output="hello",
            scoring_sheet_repository=sheet_repo,
            rubric_application_repository=rubric_repo,
            applier=applier,
        )
        second = await apply_scoring_sheet(
            tenant_context=tenant_context,
            scoring_sheet_revision_id=revision_id,
            interaction=interaction,
            output="goodbye",
            scoring_sheet_repository=sheet_repo,
            rubric_application_repository=rubric_repo,
            applier=applier,
        )

        # Read back from the DB to verify the persisted shape (not just
        # the in-memory return value).
        async with a_factory() as session:
            db_rows = (
                await session.execute(
                    sa.select(rubric_applications).order_by(
                        rubric_applications.c.created_at.asc()
                    )
                )
            ).mappings().all()

        # Cross-tenant invisibility: the eval tables exist on tenant-b
        # but no rows.
        async with b_factory() as session:
            b_count = (
                await session.execute(
                    sa.select(sa.func.count()).select_from(rubric_applications)
                )
            ).scalar_one()
            b_sheets = (
                await session.execute(
                    sa.select(sa.func.count()).select_from(scoring_sheets)
                )
            ).scalar_one()

        return {
            "first_count": len(first),
            "first_score": first[0].automated_score if first else None,
            "second_count": len(second),
            "second_score": second[0].automated_score if second else None,
            "db_row_count": len(db_rows),
            "db_scores": [r["automated_score"] for r in db_rows],
            "db_human_scores": [r["human_score"] for r in db_rows],
            "db_reviewed_by": [r["reviewed_by_user_id"] for r in db_rows],
            "db_confirmed_at": [
                r["confirmed_at"] is None for r in db_rows
            ],
            "tenant_b_rubric_application_count": b_count,
            "tenant_b_scoring_sheet_count": b_sheets,
        }
    finally:
        await a_engine.dispose()
        await b_engine.dispose()


print(json.dumps(asyncio.run(_run())))
"""


def _run_inside_api(script: str) -> dict:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "padhanam-api",
            "python",
            "-",
        ],
        cwd=os.environ.get("PADHANAM_REPO_ROOT", os.getcwd()),
        input=script,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"e2e script failed (exit {result.returncode}):"
            f"\nstderr={result.stderr!r}\nstdout={result.stdout!r}"
        )
    import json

    last = result.stdout.strip().split("\n")[-1]
    return json.loads(last)


def test_apply_scoring_sheet_end_to_end_against_tenant_a(
    compose_running: None,
) -> None:
    out = _run_inside_api(_E2E_SCRIPT)

    # First run: output='hello' matches expected_output['value']='hello'.
    assert out["first_count"] == 1
    assert out["first_score"] == "pass"

    # Second run: output='goodbye' does not match.
    assert out["second_count"] == 1
    assert out["second_score"] == "fail"

    # Two records persisted in order.
    assert out["db_row_count"] == 2
    assert out["db_scores"] == ["pass", "fail"]

    # D53 Reading-C: human-review fields stay null on every record the
    # automated path produces.
    assert out["db_human_scores"] == [None, None]
    assert out["db_reviewed_by"] == [None, None]
    assert out["db_confirmed_at"] == [True, True]


def test_tenant_b_unaffected_by_tenant_a_evaluation_writes(
    compose_running: None,
) -> None:
    """Cross-tenant invisibility: tenant-b's evaluation tables exist
    (per the migration) but carry zero rows after tenant-a's e2e flow.
    Reuses the e2e script's measurement of tenant-b counts so the
    assertion runs against the same script invocation as the positive
    case (avoiding a separate compose exec per-tenant with their own
    setup-cost overhead).
    """
    out = _run_inside_api(_E2E_SCRIPT)
    assert out["tenant_b_rubric_application_count"] == 0
    assert out["tenant_b_scoring_sheet_count"] == 0
