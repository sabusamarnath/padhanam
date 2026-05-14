"""End-to-end test for invoke_agent against the live stack (S27b → S29b).

Exercises the agent runtime end-to-end inside the padhanam-api
container against the real LiteLLM gateway and Qwen 2.5 7B via Ollama.
The test brings together every S29b commitment:

- Streaming inference (D90 commit 4): InferencePort.stream_complete
  drives the LiteLLM gateway with stream=True.
- AgentEvent vocabulary (D90 commit 2): the executor yields events
  through the loop.
- AgentLoopExecutor streaming refactor (D90 commit 5): execute() is
  an async generator yielding events.
- Nested OTel span hierarchy (D90 commit 6): agent.invocation →
  agent.iteration → gen_ai.llm_call spans on each invocation.
- invoke_agent use case refactor (D90 commit 7): the use case yields
  the event stream from the executor.
- collect_to_result helper (D90 commit 3): the test consumes the
  stream via collect_to_result to assert against the legacy
  AgentResult fields.

The in-container script:

- Wires the LiteLLM adapter with a streaming-capable capture wrapper
  recording the messages sent to the gateway across stream_complete
  calls.
- Wires the agent + audit + methodology + role + tool infrastructure
  per S28b's ToolInvoker shape (the existing wiring needed S28b's
  tool_invoker constructor update absorbed at S29b commit 9).
- Calls create_agent_from_methodology with the McKinsey methodology
  (which resolves role_refs[0] = ProblemFramer per the brief order).
- Calls invoke_agent and drives the resulting event stream end-to-end.
- Captures the full event-type sequence so the host-side assertions
  can verify D90's commitments.
- Reads back the agent's audit chain.
- Emits a single JSON line on stdout carrying the assertion-relevant
  data.

Host-side parses the JSON and asserts the D88 + D90 contract.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.live_llm  # D99: real LLM via LiteLLM/Ollama


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
            timeout=15,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return False
    return result.returncode == 0


@pytest.fixture
def stack_ready() -> None:
    if not _docker_available():
        pytest.skip("docker compose not available")

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


def test_invoke_agent_end_to_end_streaming_against_mckinsey_problem_framer(
    stack_ready: None,
) -> None:
    """Streaming whole-flow invocation: create-from-methodology then
    invoke_agent against a real LiteLLM → Ollama Qwen call (D90, S29b).

    Drives the streaming executor via invoke_agent, captures the full
    event-type sequence, collapses to AgentResult via collect_to_result
    for the legacy-shape assertions (response content, cost, audit
    hashes, termination reason).
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
    ToolDefinitionsLookupAdapter,
    ToolInvokerAdapter,
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
from contexts.agent.application.collect import collect_to_result
from contexts.audit.adapters.outbound.postgres.audit import (
    PostgresAuditAdapter,
    tenant_audit,
)
from contexts.audit.domain.events import GENESIS_HASH
from contexts.inference.adapters.outbound.litellm import LiteLLMAdapter
from contexts.inference.domain.completion import Completion, CompletionChunk, Message, ToolDefinition
from contexts.methodology.adapters.outbound.postgres import (
    MethodologyPostgresRepository,
    RolePostgresRepository,
)
from contexts.methodology.application import list_methodology_templates
from contexts.tools.adapters.outbound.postgres import ToolPostgresRepository
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import file_security_event_logger
from padhanam.security import OPERATOR_ROLE, Principal
from shared_kernel import TenantContext, TenantId


_OPERATOR = Principal(
    subject="s29b-e2e",
    tenant_id=TenantId("operator"),
    roles=frozenset({OPERATOR_ROLE}),
    credential_ref="test-token",
)


class _CapturingLiteLLM:
    '''Wraps LiteLLMAdapter, captures messages and stream-complete chunks.

    Both complete() and stream_complete() forward to the underlying
    adapter; messages and chunk counts are recorded per call so the
    host-side assertions can verify the streaming path.
    '''

    def __init__(self, inner):
        self._inner = inner
        self.captured = []  # one entry per call: {"method", "messages", "chunk_count"}

    def complete(self, messages, model, tenant_context, tools=()):
        self.captured.append(
            {
                "method": "complete",
                "messages": [
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
                ],
                "chunk_count": 0,
            }
        )
        return self._inner.complete(
            messages=messages,
            model=model,
            tenant_context=tenant_context,
            tools=tools,
        )

    async def stream_complete(self, messages, model, tenant_context, tools=()):
        call_record = {
            "method": "stream_complete",
            "messages": [
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
            ],
            "chunk_count": 0,
        }
        self.captured.append(call_record)
        async for chunk in self._inner.stream_complete(
            messages=messages,
            model=model,
            tenant_context=tenant_context,
            tools=tools,
        ):
            call_record["chunk_count"] += 1
            yield chunk


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
    tool_repo = ToolPostgresRepository.from_settings(
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
    from contexts.agent.application.ports import RetrievalResult

    class _NoRetrieval:
        async def __call__(self, **kwargs):
            return RetrievalResult()

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
        name="s29b-e2e-mckinsey",
        source_ids=(),
        actor_user_id="s29b-e2e",
    )

    real_inference = LiteLLMAdapter()
    capturing_inference = _CapturingLiteLLM(real_inference)

    # S28b two-thin-ports + S29b streaming: ToolInvokerAdapter dispatches
    # tool calls; ToolDefinitionsLookupAdapter resolves visible tools at
    # composition time. The McKinsey roles ship with empty allowlists so
    # neither port is exercised by this test; the adapters are wired so
    # the constructor shape matches the executor and use-case ports.
    tool_definitions_lookup = ToolDefinitionsLookupAdapter(
        tool_repository=tool_repo,
    )
    tool_invoker = ToolInvokerAdapter(
        tool_repository=tool_repo,
        retrieval_client=_NoRetrieval(),
        retrieval_strategy={},
        filter_tree={},
        top_k=5,
        min_score=Decimal("0.5"),
    )

    executor = AgentLoopExecutor(
        inference_port=capturing_inference,
        tool_invoker=tool_invoker,
        audit_port=audit_port,
    )

    # Drive the streaming invocation; collect events for assertion AND
    # synthesise AgentResult for the legacy-shape audit-and-cost
    # assertions per D90's collect_to_result helper.
    event_types_observed = []

    # Fake writer satisfies the S31 D95 writer parameter without
    # exercising a live Postgres write at this integration test;
    # the live-stack smoke at S31 commit 8 exercises the writer
    # against the per-tenant runs table.
    class _CapturingWriter:
        def __init__(self) -> None:
            self.calls: list = []

        async def record_run(self, record, *, principal) -> None:
            self.calls.append(record)

    writer = _CapturingWriter()

    async def event_stream_with_capture():
        async for event in invoke_agent(
            principal=_OPERATOR,
            repository=agent_repo,
            role_lookup=role_lookup,
            methodology_overrides_lookup=overrides_lookup,
            tool_definitions_lookup=tool_definitions_lookup,
            executor=executor,
            writer=writer,
            security_events=sec,
            tenant_context=tenant_ctx,
            agent_template_id=template.id,
            user_input=(
                "Help me frame the problem of declining customer retention "
                "in Q3 with explicit scope, complication, and success criteria."
            ),
        ):
            event_types_observed.append(type(event).__name__)
            yield event

    result = await collect_to_result(event_stream_with_capture())

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
    await tool_repo.dispose()

    payload = {
        "captured_calls": capturing_inference.captured,
        "event_types": event_types_observed,
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
    event_types = payload["event_types"]

    # --- D90 streaming-shape assertions ---

    # The executor goes through stream_complete (not complete) per the
    # S29b refactor.
    assert all(c["method"] == "stream_complete" for c in captured_calls), (
        f"executor should call stream_complete only at S29b; "
        f"captured methods: {[c['method'] for c in captured_calls]}"
    )
    # At least one streaming chunk arrived per LLM call.
    assert all(c["chunk_count"] >= 1 for c in captured_calls), (
        f"streaming chunks per call: {[c['chunk_count'] for c in captured_calls]}"
    )

    # Event stream starts with InvocationStarted and ends with one of
    # the three terminal-event types per D90.
    assert event_types[0] == "InvocationStarted"
    assert event_types[-1] in {
        "InvocationCompleted",
        "InvariantBlocked",
        "InvocationFailed",
    }
    # The McKinsey ProblemFramer is content-only (no tool allowlist), so
    # the terminal event is InvocationCompleted.
    assert event_types[-1] == "InvocationCompleted"
    # At least one IterationStarted, one LLMCallStarted, and one
    # ContentDelta arrived between start and terminal.
    assert "IterationStarted" in event_types
    assert "LLMCallStarted" in event_types
    assert "ContentDelta" in event_types
    assert "IterationCompleted" in event_types

    # --- D87 composition assertions (preserved from S27b) ---

    # AC #11: at least one LLM call; the first call's system message
    # contains the role base + McKinsey ProblemFramer SCQ override
    # joined by the two-newline augment separator.
    assert len(captured_calls) >= 1
    first_call_messages = captured_calls[0]["messages"]
    assert first_call_messages[0]["role"] == "system"
    system_content = first_call_messages[0]["content"]
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

    # --- D88 / D90 result-shape assertions ---

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
