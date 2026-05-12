"""End-to-end test for invoke_agent against the live stack (S27b / D88).

Exercises the first demonstrable agent invocation: a McKinsey
ProblemFramer agent (created via create_agent_from_methodology against
the McKinsey 7-Step methodology landed at S26b's 0008 migration) runs
end-to-end through the AgentLoopExecutor against the real LiteLLM
gateway and Qwen 2.5 7B via Ollama per D15. Assertions cover:

1. AC #11 — the LiteLLM adapter receives a system message containing
   both the role's base function-focused system_prompt and the McKinsey
   ProblemFramer override (the SCQ framework instruction) joined with
   the augment separator. This is the load-bearing D87 / D88 surface:
   the runtime composition reaches the LLM call.
2. AC #10 — the response is non-empty content; AgentResult carries
   cost_total_usd > 0 (or >= 0 for dev-zero model), iteration_count >= 1,
   termination_reason == "content".
3. Two audit rows landed on tenant alpha's audit chain with the
   start-then-end ordering and intact hash chain.

The test runs INSIDE the padhanam-api container via ``docker compose
exec`` so the LiteLLM gateway resolves at http://litellm:4000 and the
per-tenant Postgres at postgres-tenant-a:5432 — the same pattern as
the embedder cost-capture e2e (S20) and the create-from-methodology
e2e (S26a-2). Skip-on-unreachable behaviour matches that pattern.

The test depends on:
- McKinsey 7-Step methodology + seven roles present on control-plane
  Postgres (0008 migration applied).
- Tenant alpha database provisioned with the agent + audit tables
  (tenant Alembic chain applied).
- LiteLLM + Ollama running and serving qwen2.5:7b.
"""

from __future__ import annotations

import json
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


def _service_health(probe_url: str) -> bool:
    """Probe a service from inside the padhanam-api container via stdlib
    urllib (LiteLLM and Ollama do not ship curl)."""
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
        "postgres-control-plane",
        "postgres-tenant-a",
        "litellm",
        "ollama",
    }
    if not needed.issubset(running):
        missing = needed - running
        pytest.skip(f"compose services not running: {sorted(missing)}")
    if not _service_health("http://ollama:11434/api/tags"):
        pytest.skip("ollama health probe failed; live invocation unreachable")
    if not _service_health("http://litellm:4000/health/liveliness"):
        pytest.skip("litellm health probe failed; live invocation unreachable")


def test_invoke_agent_end_to_end_against_mckinsey_problem_framer(
    stack_ready: None,
) -> None:
    """The whole-flow invocation: create-from-methodology then
    invoke_agent against a real LiteLLM → Ollama Qwen call.

    The in-container script:
    - Wires the LiteLLM adapter with a capture-wrapper recording the
      messages sent to the gateway.
    - Wires the agent + audit + methodology + role infrastructure.
    - Calls create_agent_from_methodology with the McKinsey methodology
      (which resolves role_refs[0] = ProblemFramer per the brief order).
    - Calls invoke_agent with a sample user input.
    - Reads back the agent's audit chain.
    - Emits a single JSON line on stdout carrying the assertion-relevant
      data.

    Host-side parses the JSON and asserts the D88 contract.
    """
    script = r"""
import asyncio
import json
import sys
from decimal import Decimal
from uuid import UUID

from apps.cli._cross_context import (
    AgentRetrievalClientAdapter,
    MethodologyLookupAdapter,
    MethodologyOverridesLookupAdapter,
    RoleLookupAdapter,
    SourceLookupAdapter,
)
from apps.cli._runtime import (
    resolve_tenant_context,
    session_factory_for_tenant,
)
from contexts.agent.adapters.outbound.agent_loop_executor import (
    AgentLoopExecutor,
)
from contexts.agent.adapters.outbound.postgres import AgentPostgresRepository
from contexts.agent.application import (
    create_agent_from_methodology,
    invoke_agent,
)
from contexts.audit.adapters.outbound.postgres.audit import (
    PostgresAuditAdapter,
    tenant_audit,
)
from contexts.audit.domain.events import GENESIS_HASH
from contexts.inference.adapters.outbound.litellm import LiteLLMAdapter
from contexts.inference.domain.completion import Completion, Message, ToolDefinition
from contexts.methodology.adapters.outbound.postgres import (
    MethodologyPostgresRepository,
    RolePostgresRepository,
)
from contexts.methodology.application import list_methodology_templates
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import file_security_event_logger
from padhanam.security import OPERATOR_ROLE, Principal
from shared_kernel import TenantContext, TenantId


_OPERATOR = Principal(
    subject="s27b-e2e",
    tenant_id=TenantId("operator"),
    roles=frozenset({OPERATOR_ROLE}),
    credential_ref="test-token",
)


class _CapturingLiteLLM:
    '''Wraps LiteLLMAdapter, captures messages sent, delegates to real call.'''

    def __init__(self, inner):
        self._inner = inner
        self.captured = []

    def complete(self, messages, model, tenant_context, tools=()):
        # Capture message shapes verbatim for host-side assertion.
        self.captured.append(
            [
                {
                    "role": m.role,
                    "content": m.content,
                    "tool_calls": [
                        {"id": tc.id, "name": tc.name}
                        for tc in m.tool_calls
                    ],
                    "tool_call_id": m.tool_call_id,
                }
                for m in messages
            ]
        )
        return self._inner.complete(
            messages=messages,
            model=model,
            tenant_context=tenant_context,
            tools=tools,
        )


class _BoundResolver:
    def __init__(self, tenant_id, sessionmaker):
        self._tid = str(tenant_id)
        self._sm = sessionmaker

    async def __call__(self, tenant_id):
        if str(tenant_id) != self._tid:
            raise LookupError(f"resolver bound to {self._tid!r}")
        return self._sm


async def main() -> int:
    tenant_ctx, label = resolve_tenant_context("a")
    cp_settings = ControlPlaneSettings()
    sec = file_security_event_logger()

    tenant_engine, tenant_sm = session_factory_for_tenant(label)
    resolver = _BoundResolver(tenant_ctx.tenant_id, tenant_sm)

    agent_repo = AgentPostgresRepository(
        per_tenant_sessionmaker_resolver=resolver,
        security_events=sec,
    )
    methodology_repo = MethodologyPostgresRepository.from_settings(
        settings=cp_settings, security_events=sec
    )
    role_repo = RolePostgresRepository.from_settings(
        settings=cp_settings, security_events=sec
    )

    cp_engine = create_async_engine(
        f"postgresql+asyncpg://{cp_settings.user}:{cp_settings.password}"
        f"@{cp_settings.host}:{cp_settings.port}/{cp_settings.db}"
    )
    audit_port = PostgresAuditAdapter(
        control_plane_engine=cp_engine,
        per_tenant_sessionmaker_resolver=resolver,
    )

    # Find the McKinsey methodology on control plane.
    templates = await list_methodology_templates(
        principal=_OPERATOR, repository=methodology_repo
    )
    mckinsey = next((t for t in templates if t.name == "McKinsey 7-Step"), None)
    if mckinsey is None:
        print(json.dumps({"__skip": "McKinsey methodology not present"}))
        return 0

    methodology_lookup = MethodologyLookupAdapter(
        methodology_repository=methodology_repo,
        role_repository=role_repo,
    )
    role_lookup = RoleLookupAdapter(role_repository=role_repo)
    overrides_lookup = MethodologyOverridesLookupAdapter(
        methodology_repository=methodology_repo
    )

    # Source lookup unused in this test (no source ids passed at clone).
    class _NoSourcesLookup:
        async def assert_sources_exist(self, **kwargs):
            return None

    source_lookup = _NoSourcesLookup()

    # Retrieval client unused too (empty tool_allowlist on McKinsey roles).
    class _NoRetrieval:
        async def __call__(self, **kwargs):
            return ()

    # Create the agent from McKinsey methodology. The MethodologyLookup
    # adapter resolves role_refs[0] = ProblemFramer per the brief order.
    template, revision = await create_agent_from_methodology(
        principal=_OPERATOR,
        repository=agent_repo,
        methodology_lookup=methodology_lookup,
        source_lookup=source_lookup,
        security_events=sec,
        tenant_context=tenant_ctx,
        methodology_template_id=mckinsey.id,
        methodology_version=None,
        name="s27b-e2e-mckinsey",
        source_ids=(),
        actor_user_id="s27b-e2e",
    )

    real_inference = LiteLLMAdapter()
    capturing_inference = _CapturingLiteLLM(real_inference)

    executor = AgentLoopExecutor(
        inference_port=capturing_inference,
        retrieval_client=_NoRetrieval(),
        audit_port=audit_port,
    )

    result = await invoke_agent(
        principal=_OPERATOR,
        repository=agent_repo,
        role_lookup=role_lookup,
        methodology_overrides_lookup=overrides_lookup,
        executor=executor,
        security_events=sec,
        tenant_context=tenant_ctx,
        agent_template_id=template.id,
        user_input=(
            "Help me frame the problem of declining customer retention "
            "in Q3 with explicit scope, complication, and success criteria."
        ),
    )

    # Read the audit rows for this template id from tenant a's chain.
    async with tenant_sm() as session:
        rows_result = await session.execute(
            sa.select(
                tenant_audit.c.tenant_id,
                tenant_audit.c.action_verb,
                tenant_audit.c.resource_id,
                tenant_audit.c.previous_event_hash,
                tenant_audit.c.this_event_hash,
                tenant_audit.c.after_state,
            )
            .where(tenant_audit.c.resource_id == str(template.id))
            .order_by(
                tenant_audit.c.timestamp.asc(), tenant_audit.c.id.asc()
            )
        )
        audit_rows = [dict(r._mapping) for r in rows_result.all()]

    # Cleanup: archive the agent so re-runs don't accumulate active rows.
    await agent_repo.archive_template(template.id, tenant_ctx)

    await tenant_engine.dispose()
    await cp_engine.dispose()
    await methodology_repo.dispose()
    await role_repo.dispose()

    payload = {
        "captured_calls": capturing_inference.captured,
        "result": {
            "response_content_len": len(result.response_content),
            "response_content_first_chars": result.response_content[:200],
            "cost_total_usd": str(result.cost_total_usd),
            "iteration_count": result.iteration_count,
            "termination_reason": result.termination_reason.value,
            "audit_start_hash": result.audit_start_hash,
            "audit_end_hash": result.audit_end_hash,
            "early_termination": result.early_termination,
        },
        "audit_rows": [
            {
                "tenant_id": r["tenant_id"],
                "action_verb": r["action_verb"],
                "resource_id": r["resource_id"],
                "previous_event_hash": r["previous_event_hash"],
                "this_event_hash": r["this_event_hash"],
                "after_state": r["after_state"],
            }
            for r in audit_rows
        ],
        "expected_tenant_id": tenant_ctx.tenant_id,
        "agent_template_id": str(template.id),
    }
    print(json.dumps(payload, default=str))
    return 0


sys.exit(asyncio.run(main()))
"""

    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "padhanam-api",
            "python",
            "-c",
            script,
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, (
        f"in-container script failed (exit {result.returncode}):\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )

    # Parse JSON payload from the last stdout line.
    payload_line = result.stdout.strip().splitlines()[-1]
    payload = json.loads(payload_line)

    if "__skip" in payload:
        pytest.skip(payload["__skip"])

    captured_calls = payload["captured_calls"]
    audit_rows = payload["audit_rows"]
    agent_result = payload["result"]

    # AC #11: at least one LLM call; the first call's system message
    # contains the role base + McKinsey ProblemFramer SCQ override
    # joined by the two-newline augment separator.
    assert len(captured_calls) >= 1
    first_call = captured_calls[0]
    assert first_call[0]["role"] == "system"
    system_content = first_call[0]["content"]
    # Role base fragment (ProblemFramer function-focused prompt).
    assert "frame problems" in system_content.lower(), (
        f"role base not present in composed system prompt; got: "
        f"{system_content!r}"
    )
    # McKinsey override fragment.
    assert "SCQ framework" in system_content, (
        f"McKinsey augment override not present in composed system "
        f"prompt; got: {system_content!r}"
    )
    # The two-newline augment separator between role base and override.
    assert "\n\n" in system_content
    # The override appears AFTER the role base (augment order is role
    # base + separator + methodology value).
    role_position = system_content.lower().find("frame problems")
    scq_position = system_content.find("SCQ framework")
    assert role_position < scq_position

    # AC #10: response is non-empty content; cost >= 0; iteration_count >= 1.
    assert agent_result["response_content_len"] > 0
    assert agent_result["termination_reason"] == "content"
    assert agent_result["iteration_count"] >= 1
    assert agent_result["early_termination"] is False
    # cost_total_usd may be "0" for dev qwen2.5:7b (zero-rate pricing
    # per D62); the structural assertion is that the field exists and
    # parses as a Decimal.
    from decimal import Decimal as _D
    assert _D(agent_result["cost_total_usd"]) >= _D("0")

    # Two audit rows landed: start and end. Hash chain integrity.
    assert len(audit_rows) == 2
    assert audit_rows[0]["action_verb"] == "agent.invoke.start"
    assert audit_rows[1]["action_verb"] == "agent.invoke.end"
    assert audit_rows[0]["tenant_id"] == payload["expected_tenant_id"]
    assert audit_rows[1]["tenant_id"] == payload["expected_tenant_id"]
    assert audit_rows[0]["resource_id"] == payload["agent_template_id"]
    assert audit_rows[1]["resource_id"] == payload["agent_template_id"]
    # End chains from start; both hashes match what AgentResult surfaced.
    assert audit_rows[1]["previous_event_hash"] == audit_rows[0]["this_event_hash"]
    assert audit_rows[0]["this_event_hash"] == agent_result["audit_start_hash"]
    assert audit_rows[1]["this_event_hash"] == agent_result["audit_end_hash"]

    # End row carries the termination reason and cost.
    end_state = audit_rows[1]["after_state"]
    # JSONB roundtrips as dict or as string-encoded JSON depending on
    # the driver path; normalise either way.
    if isinstance(end_state, str):
        end_state = json.loads(end_state)
    assert end_state["termination_reason"] == "content"
    assert end_state["iteration_count"] >= 1
