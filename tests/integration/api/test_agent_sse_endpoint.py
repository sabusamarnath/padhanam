"""SSE endpoint integration tests (D90, S29b commit 8).

Drives POST /agents/{agent_id}/invoke with scripted fake dependencies
and asserts:

1. Happy-path stream produces SSE-framed events ending with an
   InvocationCompleted block.
2. Invariant-blocked stream ends with an InvariantBlocked block.
3. Failure stream ends with an InvocationFailed block.
4. Unauthenticated requests return 401 (auth middleware fires before
   the route handler).
5. Missing agent_runtime composition returns 503.

These tests use FastAPI's TestClient + dependency_overrides; the
runtime composition is a fully fake construction (fake repository,
fake lookups, fake executor that yields a scripted stream). The
live-stack integration test at commit 9 exercises the same endpoint
against the real wiring via ``docker compose exec``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, AsyncIterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.main import AppCompositions, create_app
from apps.api.routers.agent import (
    AgentRuntimeComposition,
    get_agent_runtime,
)
from apps.api.routers.inference import get_tenant_context
from contexts.agent.application.ports import RoleView
from contexts.agent.application.ports.run_history_writer import (
    AgentRunRecord,
    RunHistoryWriter,
)
from contexts.agent.domain.agent import AgentRevision, AgentTemplate
from contexts.agent.domain.events import (
    AgentEvent,
    ContentDelta,
    InvariantBlocked,
    InvocationCompleted,
    InvocationFailed,
    InvocationStarted,
    IterationCompleted,
    IterationStarted,
)
from contexts.agent.ports.executor import (
    AgentInvocationContext,
    TerminationReason,
)
from contexts.inference.domain.completion import (
    Completion,
    Message,
    TokenUsage,
)
from padhanam.events import SynchronousEventBus
from padhanam.observability.security_events import SecurityEvent
from padhanam.security.auth import issue_dev_token
from padhanam.security.hash_chain import GENESIS_REVISION_HASH
from shared_kernel import TenantContext, ToolAllowlistEntry


_TENANT_UUID = "00000000-0000-4000-8000-0000000000a1"
_AGENT_UUID = "00000000-0000-4000-8000-0000000000a9"


class _StubInferencePort:
    def complete(self, messages, model, tenant_context, tools=()) -> Completion:
        return Completion(
            text="ok",
            model=model or "stub",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )


def _tenant_context_fixture() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_UUID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_UUID,
    )


def _agent_template() -> AgentTemplate:
    return AgentTemplate(
        id=UUID(_AGENT_UUID),
        name="ProblemFramer",
        description="frames problems",
        created_by_user_id="alice",
        created_at=datetime.now(timezone.utc),
    )


def _agent_revision() -> AgentRevision:
    return AgentRevision(
        id=uuid4(),
        agent_template_id=UUID(_AGENT_UUID),
        version=1,
        system_prompt="You are a problem framer.",
        source_ids=(),
        tool_allowlist=(),
        retrieval_strategy={},
        filter_tree={},
        top_k=5,
        min_score=Decimal("0.5"),
        model_selection="qwen2.5:7b",
        created_by_user_id="alice",
        created_at=datetime.now(timezone.utc),
        previous_revision_hash=GENESIS_REVISION_HASH,
        this_revision_hash="0" * 64,
    )


class _FakeAgentRepository:
    async def get_template(self, template_id, tenant_context, version=None):
        return _agent_template(), _agent_revision()


class _FakeRoleLookup:
    async def __call__(self, *, role_id, version, principal) -> RoleView:
        raise AssertionError("blank-created agent path; role lookup not used")


class _FakeOverridesLookup:
    async def __call__(
        self,
        *,
        methodology_template_id,
        methodology_version,
        role_id,
        principal,
    ):
        return {}


async def _empty_tool_definitions_lookup(*, allowlist):
    return ()


class _ScriptedExecutor:
    """Replays a scripted event sequence for the SSE endpoint tests."""

    def __init__(self, script: list[AgentEvent]) -> None:
        self._script = script

    async def execute(
        self, context: AgentInvocationContext
    ) -> AsyncIterator[AgentEvent]:
        for event in self._script:
            yield event


class _FakeSecurityEventLogger:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


class _FakeRunHistoryWriter:
    def __init__(self) -> None:
        self.records: list[AgentRunRecord] = []

    async def record_run(self, record, *, principal) -> None:
        self.records.append(record)


def _build_app(
    *,
    runtime: AgentRuntimeComposition | None,
) -> Any:
    app = create_app(
        compositions=AppCompositions(
            inference_port=_StubInferencePort(),
            event_bus=SynchronousEventBus(),
            agent_runtime=runtime,
        ),
        configure_tracing=False,
    )
    # Override tenant context to bypass the registry resolver for this test.
    app.dependency_overrides[get_tenant_context] = lambda: _tenant_context_fixture()
    return app


def _runtime_with_script(events: list[AgentEvent]) -> AgentRuntimeComposition:
    return AgentRuntimeComposition(
        agent_repository=_FakeAgentRepository(),  # type: ignore[arg-type]
        role_lookup=_FakeRoleLookup(),  # type: ignore[arg-type]
        methodology_overrides_lookup=_FakeOverridesLookup(),  # type: ignore[arg-type]
        tool_definitions_lookup=_empty_tool_definitions_lookup,  # type: ignore[arg-type]
        executor=_ScriptedExecutor(events),  # type: ignore[arg-type]
        run_history_writer=_FakeRunHistoryWriter(),  # type: ignore[arg-type]
        security_events=_FakeSecurityEventLogger(),  # type: ignore[arg-type]
    )


def _token() -> str:
    return issue_dev_token(
        subject="alice",
        tenant_id=_TENANT_UUID,
        roles=["agent.invoke"],
    )


def _parse_sse_blocks(body: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse an SSE body into (event_type, data_dict) tuples."""
    blocks: list[tuple[str, dict[str, Any]]] = []
    raw_blocks = [b for b in body.split("\n\n") if b.strip()]
    for raw in raw_blocks:
        event_type: str | None = None
        data: dict[str, Any] | None = None
        for line in raw.splitlines():
            if line.startswith("event: "):
                event_type = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = json.loads(line.removeprefix("data: "))
        if event_type is not None and data is not None:
            blocks.append((event_type, data))
    return blocks


_INVOCATION_ID = UUID("00000000-0000-4000-8000-000000000fff")
_NOW = datetime(2026, 5, 12, 18, 0, 0, tzinfo=timezone.utc)


def test_happy_path_streams_events_ending_with_invocation_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-agent-sse")

    events: list[AgentEvent] = [
        InvocationStarted(
            invocation_id=_INVOCATION_ID,
            agent_template_id=UUID(_AGENT_UUID),
            tenant_context=_tenant_context_fixture(),
            model_name="qwen2.5:7b",
            started_at=_NOW,
        ),
        IterationStarted(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            started_at=_NOW,
        ),
        ContentDelta(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            text_fragment="Here is ",
        ),
        ContentDelta(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            text_fragment="your framed problem.",
        ),
        IterationCompleted(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            termination_signal="content",
            duration_ms=1000,
            cost_usd=Decimal("0.001"),
        ),
        InvocationCompleted(
            invocation_id=_INVOCATION_ID,
            final_result="Here is your framed problem.",
            termination_reason=TerminationReason.CONTENT,
            total_cost_usd=Decimal("0.001"),
            audit_chain_hashes=("a" * 64, "b" * 64),
            duration_ms=1500,
        ),
    ]
    runtime = _runtime_with_script(events)
    app = _build_app(runtime=runtime)
    client = TestClient(app)

    response = client.post(
        f"/agents/{_AGENT_UUID}/invoke",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"user_input": "frame this for me"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    blocks = _parse_sse_blocks(response.text)
    event_types = [t for t, _ in blocks]
    assert event_types[0] == "InvocationStarted"
    assert event_types[-1] == "InvocationCompleted"
    assert "ContentDelta" in event_types

    # InvocationCompleted's payload carries the canonical fields.
    final_event = next(d for t, d in blocks if t == "InvocationCompleted")
    assert final_event["final_result"] == "Here is your framed problem."
    assert final_event["termination_reason"] == "content"
    assert final_event["total_cost_usd"] == "0.001"
    assert final_event["audit_chain_hashes"] == ["a" * 64, "b" * 64]


def test_invariant_blocked_stream_ends_with_invariant_blocked_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-agent-sse")

    events: list[AgentEvent] = [
        InvocationStarted(
            invocation_id=_INVOCATION_ID,
            agent_template_id=UUID(_AGENT_UUID),
            tenant_context=_tenant_context_fixture(),
            model_name="qwen2.5:7b",
            started_at=_NOW,
        ),
        InvariantBlocked(
            invocation_id=_INVOCATION_ID,
            classification="financial",
            blocked_tool_name="stripe_charge",
            audit_chain_hashes=("a" * 64, "b" * 64),
        ),
    ]
    app = _build_app(runtime=_runtime_with_script(events))
    client = TestClient(app)

    response = client.post(
        f"/agents/{_AGENT_UUID}/invoke",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"user_input": "do a transfer"},
    )
    assert response.status_code == 200
    blocks = _parse_sse_blocks(response.text)
    assert blocks[-1][0] == "InvariantBlocked"
    assert blocks[-1][1]["classification"] == "financial"
    assert blocks[-1][1]["blocked_tool_name"] == "stripe_charge"


def test_invocation_failed_stream_carries_partial_audit_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-agent-sse")

    events: list[AgentEvent] = [
        InvocationStarted(
            invocation_id=_INVOCATION_ID,
            agent_template_id=UUID(_AGENT_UUID),
            tenant_context=_tenant_context_fixture(),
            model_name="qwen2.5:7b",
            started_at=_NOW,
        ),
        InvocationFailed(
            invocation_id=_INVOCATION_ID,
            error_type="TimeoutError",
            error_detail="LLM gateway timed out",
            partial_audit_chain_state=("a" * 64,),
            duration_ms=30000,
        ),
    ]
    app = _build_app(runtime=_runtime_with_script(events))
    client = TestClient(app)

    response = client.post(
        f"/agents/{_AGENT_UUID}/invoke",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"user_input": "what is LVT"},
    )
    assert response.status_code == 200
    blocks = _parse_sse_blocks(response.text)
    assert blocks[-1][0] == "InvocationFailed"
    assert blocks[-1][1]["error_type"] == "TimeoutError"
    assert blocks[-1][1]["partial_audit_chain_state"] == ["a" * 64]


def test_unauthenticated_request_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-agent-sse")
    app = _build_app(runtime=_runtime_with_script([]))
    client = TestClient(app)

    response = client.post(
        f"/agents/{_AGENT_UUID}/invoke",
        json={"user_input": "frame this"},
    )
    assert response.status_code == 401


def test_missing_runtime_composition_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-agent-sse")
    app = _build_app(runtime=None)
    client = TestClient(app)

    response = client.post(
        f"/agents/{_AGENT_UUID}/invoke",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"user_input": "frame this"},
    )
    assert response.status_code == 503
    assert "agent runtime not configured" in response.text
