"""End-to-end integration test for the eval CLI (S18).

Drives both eval commands end-to-end against tenant_a's data plane
through the live LiteLLM gateway → Ollama and the live Langfuse public
API. Verifies argument parsing, output formatting (text + JSON),
cross-tenant isolation through the CLI surface, and the integration
between the typer commands and the application-layer use cases.

Skip discriminator (matches S17b): docker compose reachable + tenant-a
+ tenant-b + litellm + ollama + padhanam-api + langfuse-web all
running, ollama health probe + Langfuse health probe via the
padhanam-api container's stdlib urllib.

Honest scope note: the dev model qwen2.5:7b is priced at 0.0 USD per
D49 (Ollama-hosted, no per-call vendor cost). The test asserts
structural correctness of the rendered output, not score accuracy.
The score quality is not meaningfully evaluated under same-model
judging (D15 dev posture); the test verifies that the report renders
with per-criterion rows and aggregate metrics, that JSON output is
parseable into the RegressionReport shape, and that cross-tenant
queries through the CLI return empty even when the trace_ids exist
in the shared Langfuse instance.

The fixture pre-populates rubric_applications by running
replay_and_score for both revisions inside the padhanam-api container
once per test module; individual tests invoke the CLI's eval report
command which reads the populated data. A separate test exercises
the eval run command (without --baseline-revision-id) to cover the
replay path through the CLI itself.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any
from uuid import UUID

import pytest


# ---------------------------------------------------------------------
# Compose probes (mirroring the S17b shape)
# ---------------------------------------------------------------------


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


def _service_healthy_via_python(probe_url: str) -> bool:
    probe = (
        "import urllib.request, sys\n"
        "try:\n"
        f"    sys.exit(0 if urllib.request.urlopen({probe_url!r}, timeout=5).status == 200 else 1)\n"
        "except Exception:\n"
        "    sys.exit(1)\n"
    )
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "padhanam-api",
                "python",
                "-c",
                probe,
            ],
            cwd=os.environ.get("PADHANAM_REPO_ROOT", os.getcwd()),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


@pytest.fixture(scope="module")
def stack_ready() -> None:
    if not _docker_available():
        pytest.skip("docker compose not reachable from test environment")
    services_run = subprocess.run(
        ["docker", "compose", "ps", "--services", "--filter", "status=running"],
        capture_output=True,
        text=True,
        check=False,
    )
    running = set(services_run.stdout.split())
    needed = {
        "padhanam-api",
        "postgres-tenant-a",
        "postgres-tenant-b",
        "litellm",
        "ollama",
        "langfuse-web",
    }
    if not needed.issubset(running):
        missing = needed - running
        pytest.skip(f"compose services not running: {sorted(missing)}")
    if not _service_healthy_via_python("http://ollama:11434/api/tags"):
        pytest.skip("ollama health probe failed; live LLM path unreachable")
    if not _service_healthy_via_python("http://langfuse-web:3000/api/public/health"):
        pytest.skip(
            "langfuse-web health probe failed; cost-query path unreachable"
        )


# ---------------------------------------------------------------------
# Setup script — inserts two revisions and populates rubric_applications
# via replay_and_score for both revisions in tenant_a's data plane.
# Runs once per test module via a module-scoped fixture; individual
# tests invoke the CLI against the cached IDs.
# ---------------------------------------------------------------------


_SETUP_SCRIPT = """
import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

# S19: bare-script TracerProvider setup lifts to the shared helper.
from padhanam.observability import init_tracing
init_tracing("padhanam-cli-e2e-setup")

from contexts.evaluation.adapters.outbound.inference_adapter import (
    InferenceAdapter,
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
from contexts.evaluation.adapters.outbound.postgres.interaction_repository import (
    PostgresInteractionRepository,
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
from contexts.evaluation.application.replay_and_score import replay_and_score
from contexts.evaluation.domain.model_config import ModelConfig
from contexts.inference.adapters.outbound.litellm import LiteLLMAdapter
from padhanam.config import InferenceSettings, TenantPostgresSettings
from shared_kernel import TenantContext


TENANT_A_UUID = "00000000-0000-4000-8000-00000000a001"


def _async_url(s):
    return f"postgresql+asyncpg://{s.user}:{s.password}@{s.host}:{s.port}/{s.db}"


async def _truncate(session_factory):
    async with session_factory() as session:
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


async def _insert_two_revision_fixtures(session_factory):
    sheet_id = uuid4()
    baseline_revision_id = uuid4()
    candidate_revision_id = uuid4()
    interaction_set_id = uuid4()
    interaction_a_id = uuid4()
    interaction_b_id = uuid4()
    now = datetime.now(timezone.utc)

    deterministic_levels = [
        {"label": "pass", "definition": "exact match", "is_success": True},
        {"label": "fail", "definition": "no match", "is_success": False},
    ]
    prompt_levels = [
        {"label": "good", "definition": "reasonable", "is_success": True},
        {"label": "bad", "definition": "unreasonable", "is_success": False},
    ]

    async with session_factory() as session:
        await session.execute(
            sa.insert(scoring_sheets).values(
                id=str(sheet_id),
                name="S18 CLI e2e sheet",
                description="CLI e2e test sheet (two revisions)",
                created_by_user_id="system:test:s18",
                created_at=now,
                archived_at=None,
            )
        )
        for revision_id, version in (
            (baseline_revision_id, 1),
            (candidate_revision_id, 2),
        ):
            await session.execute(
                sa.insert(scoring_sheet_revisions).values(
                    id=str(revision_id),
                    scoring_sheet_id=str(sheet_id),
                    version=version,
                    description=f"revision {version}",
                    created_by_user_id="system:test:s18",
                    created_at=now,
                )
            )
            det_crit_id = uuid4()
            prompt_crit_id = uuid4()
            await session.execute(
                sa.insert(scoring_sheet_criteria).values(
                    id=str(det_crit_id),
                    scoring_sheet_revision_id=str(revision_id),
                    name="exact_match_check",
                    description="output exactly equals expected",
                    levels=deterministic_levels,
                    ordering=0,
                )
            )
            await session.execute(
                sa.insert(scoring_sheet_criteria).values(
                    id=str(prompt_crit_id),
                    scoring_sheet_revision_id=str(revision_id),
                    name="answer_quality",
                    description="LLM-as-judge",
                    levels=prompt_levels,
                    ordering=1,
                )
            )
            await session.execute(
                sa.insert(appliers).values(
                    id=str(uuid4()),
                    scoring_sheet_revision_id=str(revision_id),
                    criterion_id=str(det_crit_id),
                    applier_type="deterministic",
                    deterministic_function_name="exact_match",
                    prompt_template=None,
                    judge_model=None,
                )
            )
            await session.execute(
                sa.insert(appliers).values(
                    id=str(uuid4()),
                    scoring_sheet_revision_id=str(revision_id),
                    criterion_id=str(prompt_crit_id),
                    applier_type="prompt",
                    deterministic_function_name=None,
                    prompt_template=(
                        "You are a judge. Criterion: {criterion_name}. "
                        "Allowed labels: {criterion_levels}. "
                        "Answer: {output}. "
                        "Respond with exactly one of the allowed labels."
                    ),
                    judge_model="qwen2.5:7b",
                )
            )
        await session.execute(
            sa.insert(interaction_sets).values(
                id=str(interaction_set_id),
                name="S18 CLI e2e set",
                description=None,
                created_by_user_id="system:test:s18",
                created_at=now,
            )
        )
        await session.execute(
            sa.insert(interactions).values(
                id=str(interaction_a_id),
                interaction_set_id=str(interaction_set_id),
                input={"prompt": "Reply with the single word: hello"},
                expected_output={"value": "hello"},
                ordering=0,
                created_at=now,
            )
        )
        await session.execute(
            sa.insert(interactions).values(
                id=str(interaction_b_id),
                interaction_set_id=str(interaction_set_id),
                input={"prompt": "Reply with the single word: world"},
                expected_output={"value": "world"},
                ordering=1,
                created_at=now,
            )
        )
        await session.commit()
    return baseline_revision_id, candidate_revision_id, interaction_set_id


async def _replay_revision(
    session_factory, revision_id, interaction_set_id, tenant_ctx
):
    sheet_repo = PostgresScoringSheetRepository(session_factory)
    rubric_repo = PostgresRubricApplicationRepository(session_factory)
    interaction_repo = PostgresInteractionRepository(session_factory)
    litellm_port = LiteLLMAdapter(settings=InferenceSettings())
    inference_adapter = InferenceAdapter(inference_port=litellm_port)
    applier = PolymorphicApplier(
        inference_port=inference_adapter,
        tenant_context=tenant_ctx,
    )
    await replay_and_score(
        tenant_context=tenant_ctx,
        scoring_sheet_revision_id=revision_id,
        interaction_set_id=interaction_set_id,
        model_config=ModelConfig(model_name="qwen2.5:7b"),
        inference_port=inference_adapter,
        interaction_repository=interaction_repo,
        scoring_sheet_repository=sheet_repo,
        rubric_application_repository=rubric_repo,
        applier=applier,
        apply_scoring_sheet=apply_scoring_sheet,
    )


async def _run() -> dict:
    a = TenantPostgresSettings.for_tenant("a")
    a_engine = create_async_engine(_async_url(a))
    a_factory = async_sessionmaker(a_engine, expire_on_commit=False)

    try:
        await _truncate(a_factory)
        baseline_id, candidate_id, set_id = await _insert_two_revision_fixtures(
            a_factory
        )
        tenant_a = TenantContext(
            tenant_id=TENANT_A_UUID,
            jurisdiction="eu-west",
            cost_attribution_id=TENANT_A_UUID,
        )
        await _replay_revision(a_factory, baseline_id, set_id, tenant_a)
        await _replay_revision(a_factory, candidate_id, set_id, tenant_a)

        # Force-flush spans so the cost queries (CLI runs after this)
        # find them in Langfuse. The CLI itself uses the polling
        # helper per D59, but the eval report path doesn't poll —
        # it expects historical data. The 8s sleep mirrors the S17b
        # pattern for the setup phase.
        _provider.force_flush(timeout_millis=10000)
        import time
        time.sleep(8)

        return {
            "baseline_revision_id": str(baseline_id),
            "candidate_revision_id": str(candidate_id),
            "interaction_set_id": str(set_id),
        }
    finally:
        await a_engine.dispose()


print(json.dumps(asyncio.run(_run())))
"""


def _run_inside_api(script: str, *, timeout: int = 240) -> str:
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
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"setup script failed (exit {result.returncode}):"
            f"\nstderr={result.stderr!r}\nstdout={result.stdout!r}"
        )
    return result.stdout


def _invoke_cli(args: list[str], *, timeout: int = 60) -> tuple[int, str, str]:
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
            *args,
        ],
        cwd=os.environ.get("PADHANAM_REPO_ROOT", os.getcwd()),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.fixture(scope="module")
def populated_data(stack_ready: None) -> dict[str, str]:
    out = _run_inside_api(_SETUP_SCRIPT, timeout=300)
    last = out.strip().split("\n")[-1]
    return json.loads(last)


# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------


def test_eval_report_renders_text_regression_report(
    populated_data: dict[str, str],
) -> None:
    """eval report (text format) emits a markdown regression report
    with per-criterion rows and aggregate metrics."""
    code, out, err = _invoke_cli(
        [
            "eval",
            "report",
            "--tenant-id",
            "a",
            "--baseline-revision-id",
            populated_data["baseline_revision_id"],
            "--candidate-revision-id",
            populated_data["candidate_revision_id"],
            "--interaction-set-id",
            populated_data["interaction_set_id"],
            "--output-format",
            "text",
        ]
    )
    assert code == 0, f"CLI failed:\nstdout={out!r}\nstderr={err!r}"
    assert "# Regression report" in out
    assert "Baseline revision" in out
    assert "Candidate revision" in out
    assert "## Per-criterion deltas" in out
    assert "exact_match_check" in out
    assert "answer_quality" in out
    assert "## Aggregate metrics" in out
    assert "Total baseline applications" in out
    assert "Baseline cost per task" in out


def test_eval_report_renders_json_with_regression_report_shape(
    populated_data: dict[str, str],
) -> None:
    """eval report (json format) emits parseable JSON whose shape
    matches the RegressionReport domain entity."""
    code, out, err = _invoke_cli(
        [
            "eval",
            "report",
            "--tenant-id",
            "a",
            "--baseline-revision-id",
            populated_data["baseline_revision_id"],
            "--candidate-revision-id",
            populated_data["candidate_revision_id"],
            "--interaction-set-id",
            populated_data["interaction_set_id"],
            "--output-format",
            "json",
        ]
    )
    assert code == 0, f"CLI failed:\nstdout={out!r}\nstderr={err!r}"
    data: dict[str, Any] = json.loads(out)

    # Top-level shape
    assert UUID(data["baseline_revision_id"]) == UUID(
        populated_data["baseline_revision_id"]
    )
    assert UUID(data["candidate_revision_id"]) == UUID(
        populated_data["candidate_revision_id"]
    )
    assert UUID(data["interaction_set_id"]) == UUID(
        populated_data["interaction_set_id"]
    )
    assert "generated_at" in data

    # Per-criterion deltas — both criteria present, joined by name
    delta_names = {d["criterion_name"] for d in data["per_criterion_deltas"]}
    assert delta_names == {"exact_match_check", "answer_quality"}
    for delta in data["per_criterion_deltas"]:
        assert isinstance(delta["baseline_success_rate"], (int, float))
        assert isinstance(delta["candidate_success_rate"], (int, float))
        assert isinstance(delta["delta"], (int, float))
        assert isinstance(delta["baseline_count"], int)
        assert isinstance(delta["candidate_count"], int)

    # Aggregate metrics — Decimal fields render as strings
    metrics = data["aggregate_metrics"]
    assert isinstance(metrics["baseline_cost_per_task_usd"], str)
    assert isinstance(metrics["candidate_cost_per_task_usd"], str)
    assert isinstance(metrics["overall_cost_per_task_delta_usd"], str)
    assert metrics["total_baseline_applications"] >= 1
    assert metrics["total_candidate_applications"] >= 1


def test_eval_report_cross_tenant_isolation(
    populated_data: dict[str, str],
) -> None:
    """Tenant B's invocation against tenant A's revision IDs returns
    a report with zero baseline and zero candidate applications. The
    cross-tenant invisibility holds at the CLI surface — not just at
    the trace-store layer per the S17b adapter test, but at the full
    orchestration layer the operator interacts with."""
    code, out, err = _invoke_cli(
        [
            "eval",
            "report",
            "--tenant-id",
            "b",
            "--baseline-revision-id",
            populated_data["baseline_revision_id"],
            "--candidate-revision-id",
            populated_data["candidate_revision_id"],
            "--interaction-set-id",
            populated_data["interaction_set_id"],
            "--output-format",
            "json",
        ]
    )
    assert code == 0, f"CLI failed:\nstdout={out!r}\nstderr={err!r}"
    data = json.loads(out)
    metrics = data["aggregate_metrics"]
    assert metrics["total_baseline_applications"] == 0
    assert metrics["total_candidate_applications"] == 0
    # Per-criterion deltas list is empty because no rubric_applications
    # exist in tenant B's data plane.
    assert data["per_criterion_deltas"] == []


def test_eval_run_single_revision_emits_cost_summary(
    populated_data: dict[str, str],
) -> None:
    """eval run without --baseline-revision-id replays the candidate
    revision and emits a single-run cost summary. This exercises the
    replay path through the CLI plus the D59 polling helper between
    replay and cost query.

    Honest scope note: qwen2.5:7b is priced at zero per D49, so the
    cost numbers in the rendered output are zero in the dev posture.
    The test asserts structural correctness of the rendered output
    rather than non-zero cost values.
    """
    # Replay re-uses the candidate revision; appends new rubric_applications
    # with new trace_ids. The CLI will poll for those new traces and
    # invoke the cost query.
    code, out, err = _invoke_cli(
        [
            "eval",
            "run",
            "--tenant-id",
            "a",
            "--interaction-set-id",
            populated_data["interaction_set_id"],
            "--scoring-sheet-revision-id",
            populated_data["candidate_revision_id"],
            "--output-format",
            "json",
            "--poll-timeout-seconds",
            "60.0",
        ],
        timeout=300,
    )
    assert code == 0, f"CLI failed:\nstdout={out!r}\nstderr={err!r}"
    data = json.loads(out)
    # Single-run JSON shape (cost summary, not regression report)
    assert UUID(data["candidate_revision_id"]) == UUID(
        populated_data["candidate_revision_id"]
    )
    assert UUID(data["interaction_set_id"]) == UUID(
        populated_data["interaction_set_id"]
    )
    assert data["successful_count"] >= 1
    # Decimal-as-string per the render contract
    assert isinstance(data["total_cost_usd"], str)
    assert isinstance(data["cost_per_task_usd"], str)
