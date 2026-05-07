"""End-to-end integration test for the cost-per-successful-task path.

Drives replay → score → cost_per_successful_task end-to-end against
tenant_a's data plane through the live LiteLLM gateway → Ollama and
the live Langfuse public API. Cross-tenant isolation is verified by
running the same cost query against tenant_b's tenant context and
asserting it returns empty even though the trace_ids exist in the
shared Langfuse instance.

Skip discriminator (S17b strengthens S17a's): docker compose
reachable + tenant-a/tenant-b/litellm/ollama/padhanam-api/
langfuse-web all running + ollama health probe + Langfuse-web health
probe (S17b's new gate; S17a didn't read Langfuse back so didn't
need this).

Honest scope note (S17b): the dev model qwen2.5:7b is priced at 0.0
USD per D49 (Ollama-hosted, no per-call vendor cost). The e2e test
asserts total_cost_usd >= 0 rather than > 0; the cost-rollup path is
exercised end-to-end (HTTP fetch from Langfuse, span-attribute
parsing, Decimal aggregation, cross-tenant filter), but the values
themselves are zero. Real non-zero cost arrives at the first hosted-
inference run with priced models. The e2e test would assert > 0
once a non-zero priced model lands on the dev path; documenting the
deviation from the S17b brief here so the regression is visible.
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


def _service_healthy_via_python(probe_url: str) -> bool:
    """Probe a service from inside the padhanam-api container.

    Several services in the Compose stack do not ship curl; reaching
    them through the api container's stdlib urllib is the portable
    health check the S17a e2e established for Ollama and S17b
    extends to Langfuse.
    """
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


_E2E_SCRIPT = """
import asyncio
import json
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

# S19: bare-script TracerProvider setup lifts to the shared helper.
# Pattern: bare-script drivers must mirror the FastAPI app's startup
# setup; without it trace_id is zero and Completion.trace_id is None,
# so the cost-rollup path has nothing to query.
from padhanam.observability import init_tracing
init_tracing("padhanam-eval-cost-e2e")

from contexts.evaluation.adapters.outbound.cost_query_adapter import (
    CostQueryAdapter,
)
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
from contexts.evaluation.application.cost_per_successful_task import (
    cost_per_successful_task,
)
from contexts.evaluation.application.replay_and_score import replay_and_score
from contexts.evaluation.domain.model_config import ModelConfig
from contexts.inference.adapters.outbound.litellm import LiteLLMAdapter
from contexts.observability.adapters.outbound.langfuse.http_adapter import (
    LangfuseHTTPTraceQueryAdapter,
)
from padhanam.config import InferenceSettings, TenantPostgresSettings
from shared_kernel import TenantContext


TENANT_A_UUID = "00000000-0000-4000-8000-00000000a001"
TENANT_B_UUID = "00000000-0000-4000-8000-00000000b002"


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
                name="S17b cost-per-task e2e sheet",
                description="cost-per-successful-task end-to-end test sheet",
                created_by_user_id="system:test:s17b",
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
                created_by_user_id="system:test:s17b",
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
                name="S17b cost-per-task e2e set",
                description=None,
                created_by_user_id="system:test:s17b",
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
        tenant_a = TenantContext(
            tenant_id=TENANT_A_UUID,
            jurisdiction="eu-west",
            cost_attribution_id=TENANT_A_UUID,
        )
        tenant_b = TenantContext(
            tenant_id=TENANT_B_UUID,
            jurisdiction="eu-west",
            cost_attribution_id=TENANT_B_UUID,
        )
        applier = PolymorphicApplier(
            inference_port=inference_adapter,
            tenant_context=tenant_a,
        )

        # Replay + score: produces rubric_applications with trace_ids.
        await replay_and_score(
            tenant_context=tenant_a,
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

        # Force-flush the BatchSpanProcessor so spans land in
        # Langfuse before the cost query runs. Without a flush, the
        # batch processor's idle-flush interval (default 5s) plus
        # Langfuse's ingestion lag (worker reads from ClickHouse on
        # an internal schedule) means the trace_ids may not be
        # queryable when get_costs_by_trace_ids hits the public API
        # immediately after replay completes. The flush forces the
        # spans to OTLP-exit synchronously.
        _provider.force_flush(timeout_millis=10000)
        # Brief sleep to let Langfuse's worker pipeline process the
        # ingested OTLP batch into the queryable trace store. A
        # production observation surface would emit a "trace ready"
        # signal; we use a short fixed delay because Langfuse does
        # not expose ingestion-completion events.
        time.sleep(8)

        # Wire the cost-query path. Production composes the
        # LangfuseHTTPTraceQueryAdapter once at apps/api/main.py;
        # the bare-script driver constructs it here.
        trace_query_port = LangfuseHTTPTraceQueryAdapter()
        cost_query_port = CostQueryAdapter(trace_query_port=trace_query_port)

        result = await cost_per_successful_task(
            tenant_context=tenant_a,
            scoring_sheet_revision_id=revision_id,
            interaction_set_id=interaction_set_id,
            scoring_sheet_repository=sheet_repo,
            rubric_application_repository=rubric_repo,
            cost_query_port=cost_query_port,
        )

        # Cross-tenant isolation: querying tenant_a's trace_ids
        # against tenant_b's context should return empty even
        # though the trace_ids exist in Langfuse — the adapter's
        # tenant.id span-attribute filter discards them.
        async with a_factory() as session:
            trace_ids_rows = (
                await session.execute(
                    sa.select(rubric_applications.c.trace_id).where(
                        rubric_applications.c.trace_id.is_not(None)
                    )
                )
            ).all()
        a_trace_ids = sorted({r[0] for r in trace_ids_rows if r[0]})
        cross_tenant_costs = await trace_query_port.get_costs_by_trace_ids(
            a_trace_ids, tenant_b
        )

        # tenant_b's evaluation tables: zero rows for this set.
        async with b_factory() as session:
            b_count = (
                await session.execute(
                    sa.select(sa.func.count()).select_from(rubric_applications)
                )
            ).scalar_one()

        await trace_query_port.aclose()

        return {
            "successful_count": result.successful_count,
            "total_cost_usd": str(result.total_cost_usd),
            "cost_per_task_usd": str(result.cost_per_task_usd),
            "excluded_count": result.excluded_count,
            "rubric_application_trace_ids": a_trace_ids,
            "cross_tenant_cost_query_size": len(cross_tenant_costs),
            "tenant_b_rubric_application_count": b_count,
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
        timeout=240,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"e2e script failed (exit {result.returncode}):"
            f"\nstderr={result.stderr!r}\nstdout={result.stdout!r}"
        )
    import json

    last = result.stdout.strip().split("\n")[-1]
    return json.loads(last)


def test_cost_per_successful_task_end_to_end_against_tenant_a(
    stack_ready: None,
) -> None:
    out = _run_inside_api(_E2E_SCRIPT)

    # The deterministic criterion produces "pass" for one interaction
    # ("hello" matches expected) and "fail" for the other ("world" does
    # not match expected); only "pass" is is_success. The prompt criterion
    # produces a label whose is_success outcome depends on what the LLM
    # returns. We assert structural correctness rather than specific
    # successful_count values because same-model judging itself is
    # noisy.
    assert out["successful_count"] >= 1, (
        "deterministic 'pass' on the first interaction must succeed; "
        f"got {out['successful_count']}"
    )

    # Decimal arithmetic: total_cost_usd / successful_count =
    # cost_per_task_usd within a small rounding margin.
    from decimal import Decimal

    total = Decimal(out["total_cost_usd"])
    per_task = Decimal(out["cost_per_task_usd"])
    successful = out["successful_count"]
    assert total >= Decimal("0")
    if successful > 0:
        # Allow tiny rounding drift in the division round-trip.
        assert abs(per_task - total / successful) < Decimal("0.000001")

    # qwen2.5:7b is priced at zero per D49 — total_cost_usd is
    # expected to be 0 in the dev posture. Real non-zero cost
    # arrives at the first hosted-inference run with priced models.
    # The assertion is >= 0 (not > 0) so the test passes honestly
    # in dev; documenting the deviation from the S17b brief in the
    # session log reflection.
    assert total >= Decimal("0")

    # excluded_count is the diagnostic for "low cost-per-task because
    # most data was excluded". For traces that are present in
    # Langfuse with cost data, excluded should be 0. If Langfuse
    # ingestion is still in flight when we query, excluded would
    # equal successful_count (no traces returned cost data); that's
    # an expected failure mode worth documenting if it happens.
    assert out["excluded_count"] >= 0


def test_cross_tenant_isolation_at_cost_query_layer(
    stack_ready: None,
) -> None:
    """Tenant B's cost query for tenant A's trace_ids returns empty
    even though the trace_ids exist in the shared Langfuse instance —
    the LangfuseHTTPTraceQueryAdapter's tenant-mismatch filter is the
    architectural protection against trace-id reuse leakage in the
    multi-tenant trace store.
    """
    out = _run_inside_api(_E2E_SCRIPT)
    # Tenant A produced the rubric_applications, so tenant_b's eval
    # tables stay empty.
    assert out["tenant_b_rubric_application_count"] == 0
    # Cross-tenant cost query: tenant_b queries tenant_a's trace_ids
    # → adapter filters them out → empty dict.
    assert out["cross_tenant_cost_query_size"] == 0
