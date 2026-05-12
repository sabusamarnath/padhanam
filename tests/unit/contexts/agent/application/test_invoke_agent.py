"""Unit tests for invoke_agent use case (D88, S27b).

Exercises the runtime composition path against in-memory fakes for
AgentRepositoryPort, RoleLookup, MethodologyOverridesLookup, and
AgentExecutor. Three lineage paths land:

- Blank-created agent (no role lineage): the agent's revision content
  is the role view; composition returns it unchanged.
- Role-cloned agent (only role lineage): RoleLookup re-fetches the
  role's current content; composition returns it unchanged.
- Methodology-cloned agent (both lineages): RoleLookup re-fetches the
  role; MethodologyOverridesLookup returns the per-role overrides;
  composition produces the effective bundle with augment/replace/
  tighten semantics applied per D87.

The executor fake records the AgentInvocationContext it received so
assertions verify the composed bundle reaches the executor in the
expected shape.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from contexts.agent.application import invoke_agent
from contexts.agent.application.ports import RoleView
from contexts.agent.domain.agent import AgentRevision, AgentTemplate
from contexts.agent.ports.executor import (
    AgentInvocationContext,
    AgentResult,
    TerminationReason,
)
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from padhanam.security import (
    OPERATOR_ROLE,
    AuthorizationError,
    Principal,
)
from padhanam.security.hash_chain import GENESIS_REVISION_HASH
from shared_kernel import TenantContext, TenantId, ToolAllowlistEntry


_RETRIEVAL_ENTRY = ToolAllowlistEntry(
    tool_id=UUID("00000000-0000-0000-0000-000000000001"),
    revision_id=UUID("00000000-0000-0000-0000-000000000002"),
)
_SEARCH_ENTRY = ToolAllowlistEntry(
    tool_id=UUID("00000000-0000-0000-0000-000000000010"),
    revision_id=UUID("00000000-0000-0000-0000-000000000011"),
)


async def _empty_tool_definitions_lookup(*, allowlist):
    """Fake ToolDefinitionsLookup that always returns an empty tuple.

    The invoke_agent tests do not exercise the tool surface; the
    fake stand-in lets composition return a bundle with empty
    tool_definitions, which is the Phase 1 default for any allowlist
    that doesn't pin a Phase-1-visible tool. Tests focused on the
    tool surface live at S28b commit 7's cross-context adapter
    integration tests."""
    return ()


_TENANT_A_UUID = "00000000-0000-4000-8000-00000000a001"


def _operator_principal() -> Principal:
    return Principal(
        subject="cli-operator",
        tenant_id=TenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="dev-token-op",
    )


def _unauth_principal() -> Principal:
    return Principal(
        subject="ghost",
        tenant_id=TenantId(_TENANT_A_UUID),
        roles=frozenset(),
        credential_ref="dev-token-ghost",
    )


def _tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_A_UUID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_A_UUID,
    )


def _agent_template(
    *,
    source_role_id: UUID | None = None,
    source_role_version: int | None = None,
    source_methodology_template_id: UUID | None = None,
    source_methodology_template_version: int | None = None,
) -> AgentTemplate:
    return AgentTemplate(
        id=uuid4(),
        name="Problem Framer",
        description="frames problems",
        created_by_user_id="alice",
        created_at=datetime.now(timezone.utc),
        source_role_id=source_role_id,
        source_role_version=source_role_version,
        source_methodology_template_id=source_methodology_template_id,
        source_methodology_template_version=source_methodology_template_version,
    )


def _agent_revision(template_id: UUID) -> AgentRevision:
    return AgentRevision(
        id=uuid4(),
        agent_template_id=template_id,
        version=1,
        system_prompt="You are a problem framer (revision snapshot).",
        source_ids=(),
        tool_allowlist=(_RETRIEVAL_ENTRY,),
        retrieval_strategy={"primary": "vector"},
        filter_tree={},
        top_k=8,
        min_score=Decimal("0.5"),
        model_selection="qwen2.5:7b",
        created_by_user_id="alice",
        created_at=datetime.now(timezone.utc),
        previous_revision_hash=GENESIS_REVISION_HASH,
        this_revision_hash="0" * 64,
    )


class _FakeAgentRepository:
    def __init__(self, template: AgentTemplate, revision: AgentRevision) -> None:
        self._template = template
        self._revision = revision

    async def get_template(
        self,
        template_id,
        tenant_context,
        version=None,
    ):
        return self._template, self._revision


class _ScriptedRoleLookup:
    """Records lookup args; returns a pre-canned RoleView (or raises)."""

    def __init__(self, view: RoleView | None) -> None:
        self._view = view
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self,
        *,
        role_id: UUID,
        version: int | None,
        principal: Principal,
    ) -> RoleView:
        self.calls.append(
            {"role_id": role_id, "version": version, "principal": principal}
        )
        if self._view is None:
            raise AssertionError("RoleLookup invoked but no view scripted")
        return self._view


class _ScriptedMethodologyOverridesLookup:
    """Records lookup args; returns a pre-canned overrides dict."""

    def __init__(self, overrides: dict[str, dict[str, Any]]) -> None:
        self._overrides = overrides
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self,
        *,
        methodology_template_id: UUID,
        methodology_version: int | None,
        role_id: UUID,
        principal: Principal,
    ) -> dict[str, dict[str, Any]]:
        self.calls.append(
            {
                "methodology_template_id": methodology_template_id,
                "methodology_version": methodology_version,
                "role_id": role_id,
                "principal": principal,
            }
        )
        return self._overrides


class _ScriptedExecutor:
    """Captures the AgentInvocationContext; returns a fixed AgentResult."""

    def __init__(self) -> None:
        self.captured: AgentInvocationContext | None = None

    async def execute(self, context: AgentInvocationContext) -> AgentResult:
        self.captured = context
        return AgentResult(
            response_content="ok",
            signals=(),
            cost_total_usd=Decimal("0.001"),
            iteration_count=1,
            termination_reason=TerminationReason.CONTENT,
            audit_start_hash="a" * 64,
            audit_end_hash="b" * 64,
        )


class _FakeSecurityEventLogger:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


def _mckinsey_role_view(role_id: UUID, version: int) -> RoleView:
    return RoleView(
        role_id=role_id,
        role_version=version,
        description="Frames problems for structured analysis.",
        system_prompt=(
            "You frame problems for structured analysis. Your job is to "
            "produce a sharpened problem statement."
        ),
        tool_allowlist=(_RETRIEVAL_ENTRY, _SEARCH_ENTRY),
        retrieval_strategy={"primary": "vector", "secondary": "graph"},
        filter_tree={},
        top_k=8,
        min_score=Decimal("0.5"),
        model_selection="qwen2.5:7b",
    )


# 1. Auth posture.

def test_unauthenticated_principal_raises_authorization_error() -> None:
    template = _agent_template()
    revision = _agent_revision(template.id)
    repository = _FakeAgentRepository(template, revision)
    role_lookup = _ScriptedRoleLookup(view=None)
    overrides_lookup = _ScriptedMethodologyOverridesLookup(overrides={})
    executor = _ScriptedExecutor()
    security_events = _FakeSecurityEventLogger()

    with pytest.raises(AuthorizationError):
        asyncio.run(
            invoke_agent(
                principal=_unauth_principal(),
                repository=repository,
                role_lookup=role_lookup,
                methodology_overrides_lookup=overrides_lookup,
                tool_definitions_lookup=_empty_tool_definitions_lookup,
                executor=executor,
                security_events=security_events,
                tenant_context=_tenant_context(),
                agent_template_id=template.id,
                user_input="hi",
            )
        )

    # Security-event denial emitted; executor not invoked.
    assert len(security_events.events) == 1
    assert security_events.events[0].category == SecurityEventCategory.AUTHZ_DENIAL
    assert executor.captured is None


# 2. Blank-created agent path.

def test_blank_created_agent_uses_revision_content_as_role_view() -> None:
    template = _agent_template()
    revision = _agent_revision(template.id)
    repository = _FakeAgentRepository(template, revision)
    role_lookup = _ScriptedRoleLookup(view=None)
    overrides_lookup = _ScriptedMethodologyOverridesLookup(overrides={})
    executor = _ScriptedExecutor()

    asyncio.run(
        invoke_agent(
            principal=_operator_principal(),
            repository=repository,
            role_lookup=role_lookup,
            methodology_overrides_lookup=overrides_lookup,
                tool_definitions_lookup=_empty_tool_definitions_lookup,
            executor=executor,
            security_events=_FakeSecurityEventLogger(),
            tenant_context=_tenant_context(),
            agent_template_id=template.id,
            user_input="frame the problem",
        )
    )

    assert role_lookup.calls == []  # No re-fetch when lineage is absent.
    assert overrides_lookup.calls == []
    assert executor.captured is not None
    bundle = executor.captured.effective_bundle
    # The bundle reflects the agent revision's own content.
    assert bundle.system_prompt == revision.system_prompt
    assert bundle.tool_allowlist == revision.tool_allowlist
    assert bundle.top_k == revision.top_k
    # The invocation context carries lineage sentinels for blank-created.
    assert executor.captured.methodology_template_id is None
    assert executor.captured.role_template_id == UUID(int=0)


# 3. Role-cloned agent path.

def test_role_cloned_agent_refetches_role_no_methodology_overrides() -> None:
    role_id = uuid4()
    template = _agent_template(source_role_id=role_id, source_role_version=2)
    revision = _agent_revision(template.id)
    role_view = _mckinsey_role_view(role_id, 2)
    repository = _FakeAgentRepository(template, revision)
    role_lookup = _ScriptedRoleLookup(view=role_view)
    overrides_lookup = _ScriptedMethodologyOverridesLookup(overrides={})
    executor = _ScriptedExecutor()

    asyncio.run(
        invoke_agent(
            principal=_operator_principal(),
            repository=repository,
            role_lookup=role_lookup,
            methodology_overrides_lookup=overrides_lookup,
                tool_definitions_lookup=_empty_tool_definitions_lookup,
            executor=executor,
            security_events=_FakeSecurityEventLogger(),
            tenant_context=_tenant_context(),
            agent_template_id=template.id,
            user_input="frame the problem",
        )
    )

    assert len(role_lookup.calls) == 1
    assert role_lookup.calls[0]["role_id"] == role_id
    assert role_lookup.calls[0]["version"] == 2
    # No methodology lineage so no overrides lookup.
    assert overrides_lookup.calls == []
    # Effective bundle equals role view's content; no methodology overlay.
    assert executor.captured is not None
    bundle = executor.captured.effective_bundle
    assert bundle.system_prompt == role_view.system_prompt
    assert bundle.tool_allowlist == role_view.tool_allowlist


# 4. Methodology-cloned agent path: augment composition reaches the executor.

def test_methodology_cloned_agent_applies_augment_override() -> None:
    """The McKinsey ProblemFramer case at the use case level: the role
    is re-fetched, the methodology's augment-mode system_prompt override
    is applied, the effective bundle reaches the executor with the
    composed system_prompt."""
    role_id = uuid4()
    methodology_id = uuid4()
    template = _agent_template(
        source_role_id=role_id,
        source_role_version=1,
        source_methodology_template_id=methodology_id,
        source_methodology_template_version=1,
    )
    revision = _agent_revision(template.id)
    role_view = _mckinsey_role_view(role_id, 1)
    repository = _FakeAgentRepository(template, revision)
    role_lookup = _ScriptedRoleLookup(view=role_view)
    overrides_lookup = _ScriptedMethodologyOverridesLookup(
        overrides={
            "system_prompt": {
                "mode": "augment",
                "value": (
                    "Apply the SCQ framework (Situation, Complication, "
                    "Question) when framing."
                ),
            },
        }
    )
    executor = _ScriptedExecutor()

    asyncio.run(
        invoke_agent(
            principal=_operator_principal(),
            repository=repository,
            role_lookup=role_lookup,
            methodology_overrides_lookup=overrides_lookup,
                tool_definitions_lookup=_empty_tool_definitions_lookup,
            executor=executor,
            security_events=_FakeSecurityEventLogger(),
            tenant_context=_tenant_context(),
            agent_template_id=template.id,
            user_input="declining customer retention in Q3",
        )
    )

    # Both lookups invoked.
    assert len(role_lookup.calls) == 1
    assert len(overrides_lookup.calls) == 1
    assert overrides_lookup.calls[0]["methodology_template_id"] == methodology_id
    assert overrides_lookup.calls[0]["role_id"] == role_id

    # The effective bundle's system_prompt is role_base + "\n\n" + override.
    assert executor.captured is not None
    bundle = executor.captured.effective_bundle
    assert role_view.system_prompt in bundle.system_prompt
    assert "SCQ framework" in bundle.system_prompt
    assert role_view.system_prompt + "\n\n" in bundle.system_prompt

    # AgentInvocationContext carries the methodology lineage.
    assert executor.captured.methodology_template_id == methodology_id
    assert executor.captured.methodology_version == 1
    assert executor.captured.role_template_id == role_id


def test_methodology_cloned_with_empty_overrides_returns_role_base() -> None:
    """A role that's part of a methodology revision but has empty
    overrides for that role returns the role base unchanged."""
    role_id = uuid4()
    methodology_id = uuid4()
    template = _agent_template(
        source_role_id=role_id,
        source_role_version=1,
        source_methodology_template_id=methodology_id,
        source_methodology_template_version=1,
    )
    revision = _agent_revision(template.id)
    role_view = _mckinsey_role_view(role_id, 1)
    repository = _FakeAgentRepository(template, revision)
    role_lookup = _ScriptedRoleLookup(view=role_view)
    overrides_lookup = _ScriptedMethodologyOverridesLookup(overrides={})
    executor = _ScriptedExecutor()

    asyncio.run(
        invoke_agent(
            principal=_operator_principal(),
            repository=repository,
            role_lookup=role_lookup,
            methodology_overrides_lookup=overrides_lookup,
                tool_definitions_lookup=_empty_tool_definitions_lookup,
            executor=executor,
            security_events=_FakeSecurityEventLogger(),
            tenant_context=_tenant_context(),
            agent_template_id=template.id,
            user_input="hi",
        )
    )

    assert executor.captured is not None
    bundle = executor.captured.effective_bundle
    assert bundle.system_prompt == role_view.system_prompt
