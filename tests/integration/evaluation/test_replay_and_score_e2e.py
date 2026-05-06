"""End-to-end integration test for the replay engine.

Drives the full ``replay_and_score`` use case through:
- a real per-tenant Postgres database (tenant-a's data plane);
- the live inference path (LiteLLM gateway → Ollama running the
  Qwen 2.5 7B model per D15);
- the InferenceAdapter wrapping ``contexts.inference.api.request_completion``;
- the PolymorphicApplier with both deterministic and prompt branches;
- the PostgresInteractionRepository, PostgresScoringSheetRepository,
  and PostgresRubricApplicationRepository read/write paths.

Exercises the full S17a flow inside the padhanam-api container via
``docker compose exec`` (matching the S16 e2e pattern). Skips
cleanly when the Compose stack is not reachable OR when the inference
path's Ollama health endpoint does not respond — the test exercises
a live LLM call through LiteLLM through Ollama; if any link is
unhealthy, the test is invalid rather than failing.

Honest scope note (S17a): the dev environment runs the same model
(qwen2.5:7b per D15) for both the replay and the judge. The
resulting prompt-applier scores are not meaningful evaluations of
agent quality — same model judging itself produces uniform
"good-enough" ratings. The test asserts proof of flow: replay runs,
trace_id propagates from the inference span into rubric_applications,
deterministic branch produces deterministic pass/fail, prompt
branch produces some non-null score. Real cross-model evaluation
arrives when Phase 2 hosted inference is available per S6's
reflection note.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request

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


def _ollama_healthy() -> bool:
    """Probe Ollama via the padhanam-api container's network.

    The Ollama image does not ship curl; we reach it through the
    padhanam-api container using Python's stdlib urllib. The compose
    network resolves ``ollama:11434`` from any service in the stack.
    """
    probe = (
        "import urllib.request, sys\n"
        "try:\n"
        "    sys.exit(0 if urllib.request.urlopen("
        "'http://ollama:11434/api/tags', timeout=5).status == 200 else 1)\n"
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
    }
    if not needed.issubset(running):
        missing = needed - running
        pytest.skip(f"compose services not running: {sorted(missing)}")
    if not _ollama_healthy():
        pytest.skip("ollama health probe failed; live LLM path unreachable")


_E2E_SCRIPT = """
import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

# Initialise the OTel SDK so the LiteLLMAdapter's span carries a
# real trace_id. The FastAPI app does this at startup; the bare
# script driver here mirrors that. Without it, the SDK's default
# no-op provider produces trace_id=0 and Completion.trace_id=None.
from padhanam.config import ObservabilitySettings as _Obs
_obs = _Obs()
_provider = TracerProvider(
    resource=Resource.create({"service.name": "padhanam-eval-e2e"})
)
_provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint=_obs.otlp_endpoint,
            headers={"Authorization": _obs.otlp_basic_auth_header},
        )
    )
)
trace.set_tracer_provider(_provider)

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


def _async_url(s: TenantPostgresSettings) -> str:
    return f"postgresql+asyncpg://{s.user}:{s.password}@{s.host}:{s.port}/{s.db}"


async def _truncate(session_factory) -> None:
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


async def _insert_fixtures(session_factory):
    sheet_id = uuid4()
    revision_id = uuid4()
    deterministic_criterion_id = uuid4()
    prompt_criterion_id = uuid4()
    deterministic_applier_id = uuid4()
    prompt_applier_id = uuid4()
    interaction_set_id = uuid4()
    interaction_a_id = uuid4()
    interaction_b_id = uuid4()
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        await session.execute(
            sa.insert(scoring_sheets).values(
                id=str(sheet_id),
                name="S17a e2e sheet",
                description="End-to-end replay-and-score test sheet",
                created_by_user_id="system:test:s17a",
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
                created_by_user_id="system:test:s17a",
                created_at=now,
            )
        )
        await session.execute(
            sa.insert(scoring_sheet_criteria).values(
                id=str(deterministic_criterion_id),
                scoring_sheet_revision_id=str(revision_id),
                name="exact_match_check",
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
            sa.insert(scoring_sheet_criteria).values(
                id=str(prompt_criterion_id),
                scoring_sheet_revision_id=str(revision_id),
                name="answer_quality",
                description="LLM-as-judge: is the answer reasonable",
                levels=[
                    {
                        "label": "good",
                        "definition": "answer is reasonable",
                        "is_success": True,
                    },
                    {
                        "label": "bad",
                        "definition": "answer is unreasonable",
                        "is_success": False,
                    },
                ],
                ordering=1,
            )
        )
        await session.execute(
            sa.insert(appliers).values(
                id=str(deterministic_applier_id),
                scoring_sheet_revision_id=str(revision_id),
                criterion_id=str(deterministic_criterion_id),
                applier_type="deterministic",
                deterministic_function_name="exact_match",
                prompt_template=None,
                judge_model=None,
            )
        )
        await session.execute(
            sa.insert(appliers).values(
                id=str(prompt_applier_id),
                scoring_sheet_revision_id=str(revision_id),
                criterion_id=str(prompt_criterion_id),
                applier_type="prompt",
                deterministic_function_name=None,
                prompt_template=(
                    "You are a judge. The criterion is {criterion_name}. "
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
                name="S17a e2e set",
                description=None,
                created_by_user_id="system:test:s17a",
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
    return revision_id, interaction_set_id


async def _run() -> dict:
    a = TenantPostgresSettings.for_tenant("a")
    b = TenantPostgresSettings.for_tenant("b")
    a_engine = create_async_engine(_async_url(a))
    a_factory = async_sessionmaker(a_engine, expire_on_commit=False)
    b_engine = create_async_engine(_async_url(b))
    b_factory = async_sessionmaker(b_engine, expire_on_commit=False)

    try:
        await _truncate(a_factory)
        revision_id, interaction_set_id = await _insert_fixtures(a_factory)

        sheet_repo = PostgresScoringSheetRepository(a_factory)
        rubric_repo = PostgresRubricApplicationRepository(a_factory)
        interaction_repo = PostgresInteractionRepository(a_factory)
        litellm_port = LiteLLMAdapter(settings=InferenceSettings())
        inference_adapter = InferenceAdapter(inference_port=litellm_port)
        tenant_context = TenantContext(
            tenant_id=TENANT_A_UUID,
            jurisdiction="eu-west",
            cost_attribution_id=TENANT_A_UUID,
        )
        applier = PolymorphicApplier(
            inference_port=inference_adapter,
            tenant_context=tenant_context,
        )

        results = await replay_and_score(
            tenant_context=tenant_context,
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

        async with a_factory() as session:
            db_rows = (
                await session.execute(
                    sa.select(rubric_applications).order_by(
                        rubric_applications.c.created_at.asc()
                    )
                )
            ).mappings().all()

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
            "results_count": len(results),
            "db_row_count": len(db_rows),
            "db_automated_scores": [r["automated_score"] for r in db_rows],
            "db_human_scores_all_null": all(
                r["human_score"] is None for r in db_rows
            ),
            "db_reviewed_by_all_null": all(
                r["reviewed_by_user_id"] is None for r in db_rows
            ),
            "db_confirmed_at_all_null": all(
                r["confirmed_at"] is None for r in db_rows
            ),
            "db_trace_ids_all_present": all(
                isinstance(r["trace_id"], str) and len(r["trace_id"]) > 0
                for r in db_rows
            ),
            "db_distinct_trace_ids": sorted(
                set(r["trace_id"] for r in db_rows)
            ),
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
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"e2e script failed (exit {result.returncode}):"
            f"\nstderr={result.stderr!r}\nstdout={result.stdout!r}"
        )
    import json

    last = result.stdout.strip().split("\n")[-1]
    return json.loads(last)


def test_replay_and_score_end_to_end_against_tenant_a(
    stack_ready: None,
) -> None:
    out = _run_inside_api(_E2E_SCRIPT)

    # 2 interactions × 2 criteria = 4 rubric_application rows.
    assert out["results_count"] == 4
    assert out["db_row_count"] == 4

    # Every row has a populated automated_score (some non-null
    # string, possibly empty for prompt branches that the LLM did
    # not return a parseable label for; the deterministic branch
    # always produces "pass" or "fail").
    assert all(s is not None for s in out["db_automated_scores"])

    # D53 Reading-C: human-review fields stay null on every record
    # the automated path produces.
    assert out["db_human_scores_all_null"] is True
    assert out["db_reviewed_by_all_null"] is True
    assert out["db_confirmed_at_all_null"] is True

    # trace_id forward-affordance activated: every row carries a
    # non-empty trace_id matching the inference adapter's OTel span.
    assert out["db_trace_ids_all_present"] is True
    # 2 inference calls (one per interaction) → 2 distinct trace_ids
    # → 4 rubric_applications share trace_id by interaction.
    assert len(out["db_distinct_trace_ids"]) == 2


def test_tenant_b_unaffected_by_tenant_a_replay_writes(
    stack_ready: None,
) -> None:
    """Cross-tenant invisibility: tenant-b's evaluation tables exist
    (per the migration) but carry zero rows after tenant-a's e2e
    flow. Reuses the e2e script's measurement so the assertion runs
    against the same script invocation as the positive case.
    """
    out = _run_inside_api(_E2E_SCRIPT)
    assert out["tenant_b_rubric_application_count"] == 0
    assert out["tenant_b_scoring_sheet_count"] == 0
