"""POST /agents/{agent_id}/invoke — SSE streaming agent invocation (D90, S29b).

Translates the agent runtime's ``AgentEvent`` stream into Server-Sent
Events for clients. The URL shape follows the existing ``apps/api/``
convention (principal-derived tenant context; no
``/tenants/{tenant_id}/...`` path prefix) per the S29b pre-write
reconciliation against ``/inference/completions`` and ``/tenant/audit``.

The route is thin: it resolves dependencies from ``app.state``, calls
``contexts.agent.application.invoke_agent`` (which returns
``AsyncIterator[AgentEvent]``), and wraps the stream in
``StreamingResponse`` with ``media_type="text/event-stream"``. The
domain-to-wire translation lives at
``apps/api/adapters/sse_event_translator.py``.

Dependency wiring at production composition time happens in
``apps/api/main.py`` via the ``AppCompositions.agent_runtime`` field;
tests substitute the dependencies via ``app.dependency_overrides``
similar to the existing inference router pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from apps.api.adapters.sse_event_translator import translate_event_to_sse
from apps.api.middleware import get_principal
from apps.api.routers.inference import get_tenant_context
from contexts.agent.application import invoke_agent
from contexts.agent.application.ports import (
    MethodologyOverridesLookup,
    RoleLookup,
    ToolDefinitionsLookup,
)
from contexts.agent.ports import AgentExecutor, AgentRepositoryPort
from padhanam.observability.security_events import (
    SecurityEventLogger,
    file_security_event_logger,
)
from padhanam.security import Principal
from shared_kernel import TenantContext


router = APIRouter(prefix="/agents", tags=["agents"])


@dataclass(frozen=True)
class AgentRuntimeComposition:
    """The dependencies the SSE route needs to drive ``invoke_agent``.

    Production wiring constructs this in ``apps/api/main.py``'s
    ``_build_default_compositions``; tests substitute via FastAPI's
    ``app.dependency_overrides`` mechanism on the ``get_agent_runtime``
    dependency function. The composition is kept on ``app.state``
    alongside the existing ``inference_port`` and ``audit_port``
    seams.
    """

    agent_repository: AgentRepositoryPort
    role_lookup: RoleLookup
    methodology_overrides_lookup: MethodologyOverridesLookup
    tool_definitions_lookup: ToolDefinitionsLookup
    executor: AgentExecutor
    security_events: SecurityEventLogger


class InvokeAgentRequest(BaseModel):
    """Inbound payload for POST /agents/{agent_id}/invoke."""

    user_input: str = Field(min_length=1)


def get_agent_runtime(request: Request) -> AgentRuntimeComposition:
    """FastAPI dependency that pulls the configured agent runtime composition.

    apps/api/main.py registers the composition on ``app.state.agent_runtime``
    at application-factory time when production wiring is in place;
    tests override this dependency via
    ``app.dependency_overrides[get_agent_runtime]`` to substitute fakes.
    Returns 503 when no runtime composition is configured (e.g.,
    apps without the agent stack wired).
    """
    runtime = getattr(request.app.state, "agent_runtime", None)
    if runtime is None:
        raise HTTPException(
            status_code=503,
            detail="agent runtime not configured on this API instance",
        )
    return runtime


@router.post("/{agent_id}/invoke")
async def invoke_agent_endpoint(
    agent_id: UUID,
    body: InvokeAgentRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    runtime: Annotated[AgentRuntimeComposition, Depends(get_agent_runtime)],
    principal: Annotated[Principal, Depends(get_principal)],
) -> StreamingResponse:
    """Stream an agent invocation as SSE.

    The route returns immediately with a StreamingResponse whose body
    is an async generator yielding SSE-formatted strings. The agent
    runtime's per-event yield drives the response chunk-by-chunk to
    the client.

    Errors raised before the first yield (auth denial, agent not
    found, etc.) surface as standard HTTP error responses; errors
    after the first yield surface as ``InvocationFailed`` events
    inside the stream per D90's terminal-event vocabulary.
    """

    async def event_stream() -> AsyncIterator[bytes]:
        async for event in invoke_agent(
            principal=principal,
            repository=runtime.agent_repository,
            role_lookup=runtime.role_lookup,
            methodology_overrides_lookup=runtime.methodology_overrides_lookup,
            tool_definitions_lookup=runtime.tool_definitions_lookup,
            executor=runtime.executor,
            security_events=runtime.security_events,
            tenant_context=tenant_context,
            agent_template_id=agent_id,
            user_input=body.user_input,
        ):
            yield translate_event_to_sse(event).encode("utf-8")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )


def _default_security_events() -> SecurityEventLogger:
    """Convenience constructor for tests that don't substitute the logger."""
    return file_security_event_logger()
