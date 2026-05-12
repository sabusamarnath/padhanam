"""Tenant isolation contract test for the SSE streaming agent path (D32, D90; S29b commit 9).

The SSE endpoint at ``POST /agents/{agent_id}/invoke`` resolves
``TenantContext`` from the authenticated principal's tenant_id (via
the existing ``get_tenant_context`` dependency from S15). This contract
test verifies that the tenant context threaded through to
``invoke_agent``, and onward to the executor, matches the bearer
token's tenant — there is no cross-tenant attack vector at the route
layer (no ``/tenants/{tenant_id}/...`` path-param that could be
substituted for a different tenant).

The test instruments the streaming runtime with a recording executor
that captures the ``AgentInvocationContext.tenant_context`` it
received. Two bearer tokens (one for tenant A, one for tenant B) drive
two requests; each tenant_context recorded by the executor must match
the bearer token's tenant. Cross-tenant leak (executor seeing tenant A
context for a tenant-B token) would fail the assertion.

This is the in-process complement to the live-stack end-to-end test at
``tests/integration/contexts/agent/test_invoke_agent_end_to_end.py``;
the live test verifies audit chain isolation, while this contract test
verifies the tenant-context routing at the SSE endpoint.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncIterator
from uuid import UUID, uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from apps.api.main import AppCompositions, create_app
from apps.api.routers.agent import (
    AgentRuntimeComposition,
    get_agent_runtime,
)
from apps.api.routers.inference import get_tenant_context
from contexts.agent.application.ports import RoleView
from contexts.agent.domain.agent import AgentRevision, AgentTemplate
from contexts.agent.domain.events import (
    AgentEvent,
    InvocationCompleted,
    InvocationStarted,
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
from shared_kernel import TenantContext


_TENANT_A = "00000000-0000-4000-8000-00000000a001"
_TENANT_B = "00000000-0000-4000-8000-00000000b002"
_AGENT_UUID = "00000000-0000-4000-8000-0000000000ee"


class _StubInferencePort:
    def complete(self, messages, model, tenant_context, tools=()) -> Completion:
        return Completion(
            text="ok",
            model=model or "stub",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )


def _tenant_context(uuid: str) -> TenantContext:
    return TenantContext(
        tenant_id=uuid,
        jurisdiction="eu-west",
        cost_attribution_id=uuid,
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
    def __init__(self) -> None:
        self.captured_contexts: list[TenantContext] = []

    async def get_template(self, template_id, tenant_context, version=None):
        self.captured_contexts.append(tenant_context)
        return _agent_template(), _agent_revision()


class _FakeRoleLookup:
    async def __call__(self, *, role_id, version, principal) -> RoleView:
        raise AssertionError("blank-created agent; role lookup not used")


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


class _CapturingExecutor:
    """Records the AgentInvocationContext it received per execute() call."""

    def __init__(self) -> None:
        self.captured: list[AgentInvocationContext] = []

    async def execute(
        self, context: AgentInvocationContext
    ) -> AsyncIterator[AgentEvent]:
        self.captured.append(context)
        yield InvocationStarted(
            invocation_id=UUID(int=1),
            agent_template_id=context.agent_template_id,
            tenant_context=context.tenant_context,
            model_name=context.effective_bundle.model_selection,
            started_at=datetime.now(timezone.utc),
        )
        yield InvocationCompleted(
            invocation_id=UUID(int=1),
            final_result="ok",
            termination_reason=TerminationReason.CONTENT,
            total_cost_usd=Decimal("0"),
            audit_chain_hashes=("a" * 64, "b" * 64),
            duration_ms=10,
        )


class _FakeSecurityEventLogger:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


def _build_app(executor: _CapturingExecutor, repo: _FakeAgentRepository):
    runtime = AgentRuntimeComposition(
        agent_repository=repo,  # type: ignore[arg-type]
        role_lookup=_FakeRoleLookup(),  # type: ignore[arg-type]
        methodology_overrides_lookup=_FakeOverridesLookup(),  # type: ignore[arg-type]
        tool_definitions_lookup=_empty_tool_definitions_lookup,  # type: ignore[arg-type]
        executor=executor,  # type: ignore[arg-type]
        security_events=_FakeSecurityEventLogger(),  # type: ignore[arg-type]
    )
    app = create_app(
        compositions=AppCompositions(
            inference_port=_StubInferencePort(),
            event_bus=SynchronousEventBus(),
            agent_runtime=runtime,
        ),
        configure_tracing=False,
    )
    # Override tenant context to bypass the registry resolver. The
    # override reads the request's principal and constructs the matching
    # TenantContext, mirroring the production path's behaviour without
    # requiring a live registry.
    def _resolve_from_principal_state(request: Request) -> TenantContext:
        principal = request.state.principal
        return _tenant_context(str(principal.tenant_id))

    app.dependency_overrides[get_tenant_context] = _resolve_from_principal_state
    return app


def test_streaming_endpoint_threads_correct_tenant_per_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two requests with different tenant bearer tokens reach the
    executor with their respective tenant contexts; no cross-tenant
    leak at the SSE endpoint layer."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-isolation")

    executor = _CapturingExecutor()
    repo = _FakeAgentRepository()
    app = _build_app(executor, repo)
    client = TestClient(app)

    token_a = issue_dev_token(
        subject="alice", tenant_id=_TENANT_A, roles=["agent.invoke"]
    )
    token_b = issue_dev_token(
        subject="bob", tenant_id=_TENANT_B, roles=["agent.invoke"]
    )

    response_a = client.post(
        f"/agents/{_AGENT_UUID}/invoke",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"user_input": "tenant A query"},
    )
    response_b = client.post(
        f"/agents/{_AGENT_UUID}/invoke",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"user_input": "tenant B query"},
    )

    assert response_a.status_code == 200
    assert response_b.status_code == 200

    # Executor saw two invocations, one per tenant.
    assert len(executor.captured) == 2
    contexts_by_tenant = {c.tenant_context.tenant_id for c in executor.captured}
    assert contexts_by_tenant == {_TENANT_A, _TENANT_B}

    # Tenant A's request reached the executor with tenant A's context;
    # tenant B's request reached with tenant B's context. No swap.
    first_ctx = executor.captured[0].tenant_context
    second_ctx = executor.captured[1].tenant_context
    assert first_ctx.tenant_id == _TENANT_A
    assert second_ctx.tenant_id == _TENANT_B

    # Agent repository fetched with the matching tenant_context on each
    # call (i.e., the SSE route's get_tenant_context resolved before
    # invoke_agent's repository lookup).
    assert len(repo.captured_contexts) == 2
    assert repo.captured_contexts[0].tenant_id == _TENANT_A
    assert repo.captured_contexts[1].tenant_id == _TENANT_B


def test_streaming_endpoint_unauthenticated_rejected_before_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auth middleware fires before the route handler; the executor is
    never invoked for an unauthenticated request, so no tenant context
    is fabricated."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-isolation")

    executor = _CapturingExecutor()
    repo = _FakeAgentRepository()
    app = _build_app(executor, repo)
    client = TestClient(app)

    response = client.post(
        f"/agents/{_AGENT_UUID}/invoke",
        json={"user_input": "anonymous attempt"},
    )

    assert response.status_code == 401
    assert executor.captured == []
    assert repo.captured_contexts == []
