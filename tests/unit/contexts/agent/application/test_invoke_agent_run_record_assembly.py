"""Unit tests for the invoke_agent run-record assembly seam (D95, S31 commit 6).

Five concerns covering the four termination paths plus auth-failure
plus the shape-B write-timing ordering commitment:

1. InvocationCompleted: writer.record_run is called with a record
   carrying termination_reason from event.termination_reason.value,
   both audit hashes from event.audit_chain_hashes, output_content
   from event.final_result, total_cost_usd from event.total_cost_usd.

2. InvariantBlocked: writer.record_run is called with
   termination_reason='invariant_blocked', both audit hashes from
   event.audit_chain_hashes, output_content empty, total_cost_usd
   from the accumulated IterationCompleted events.

3. InvocationFailed with 1-hash partial_audit_chain_state (the
   currently-fired case from the executor's loop-body-exception and
   end-audit-emission-failure sites): writer.record_run is called
   with termination_reason='failed', audit_end_hash=None, output_content
   empty.

4. InvocationFailed with 0-hash partial_audit_chain_state
   (pre-start-audit failure): writer.record_run is NOT called per
   the projection-over-recorded-activity framing.

5. Auth-failure: writer.record_run is NOT called because the auth
   check fires at first __anext__ before any event yields.

Plus the ordering invariant (shape B per D95): the terminal event
is yielded to the consumer BEFORE writer.record_run is called.
A shared call-ordering list captures the sequence.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from contexts.agent.application import invoke_agent
from contexts.agent.application.ports import AgentRunRecord, RoleView
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
from padhanam.observability.security_events import SecurityEvent
from padhanam.security import (
    OPERATOR_ROLE,
    AuthorizationError,
    Principal,
)
from padhanam.security.hash_chain import GENESIS_REVISION_HASH
from shared_kernel import TenantContext, TenantId, ToolAllowlistEntry


_TENANT_A = "00000000-0000-4000-8000-00000000a001"
_INVOCATION_ID = UUID("00000000-0000-4000-8000-0000000000aa")
_START_HASH = "0" * 64
_END_HASH = "1" * 64


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
        tenant_id=TenantId(_TENANT_A),
        roles=frozenset(),
        credential_ref="dev-token-ghost",
    )


def _tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_A,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_A,
    )


def _agent_template() -> AgentTemplate:
    return AgentTemplate(
        id=uuid4(),
        name="Problem Framer",
        description="frames problems",
        created_by_user_id="alice",
        created_at=datetime.now(timezone.utc),
    )


def _agent_revision(template_id: UUID) -> AgentRevision:
    return AgentRevision(
        id=uuid4(),
        agent_template_id=template_id,
        version=1,
        system_prompt="You frame problems.",
        source_ids=(),
        tool_allowlist=(),
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
    def __init__(
        self, template: AgentTemplate, revision: AgentRevision
    ) -> None:
        self._template = template
        self._revision = revision

    async def get_template(
        self, template_id, tenant_context, version=None
    ):
        return self._template, self._revision


class _NoopRoleLookup:
    async def __call__(self, *, role_id, version, principal):
        raise AssertionError("RoleLookup invoked for blank-created agent")


class _NoopOverridesLookup:
    async def __call__(
        self, *, methodology_template_id, methodology_version, role_id, principal
    ):
        return {}


async def _empty_tool_definitions_lookup(*, allowlist):
    return ()


class _ScriptedExecutor:
    """Yields a scripted event stream for run-record assembly tests."""

    def __init__(self, events: list[AgentEvent]) -> None:
        self._events = events

    async def execute(self, context: AgentInvocationContext):
        for event in self._events:
            yield event


class _FakeSecurityEventLogger:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


class _FakeRunHistoryWriter:
    """Captures record_run calls. Optionally records a shared ordering log."""

    def __init__(self, ordering_log: list[str] | None = None) -> None:
        self.calls: list[AgentRunRecord] = []
        self._ordering_log = ordering_log

    async def record_run(
        self, record: AgentRunRecord, *, principal: Principal
    ) -> None:
        self.calls.append(record)
        if self._ordering_log is not None:
            self._ordering_log.append("writer.record_run")


def _start_event(template_id: UUID) -> InvocationStarted:
    return InvocationStarted(
        invocation_id=_INVOCATION_ID,
        agent_template_id=template_id,
        tenant_context=_tenant_context(),
        model_name="qwen2.5:7b",
        started_at=datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc),
    )


def _iter_started(idx: int) -> IterationStarted:
    return IterationStarted(
        invocation_id=_INVOCATION_ID,
        iteration_index=idx,
        started_at=datetime.now(timezone.utc),
    )


def _iter_completed(idx: int, cost: Decimal) -> IterationCompleted:
    return IterationCompleted(
        invocation_id=_INVOCATION_ID,
        iteration_index=idx,
        termination_signal="content",
        duration_ms=50,
        cost_usd=cost,
    )


def _drive(events) -> list[AgentEvent]:
    async def _collect() -> list[AgentEvent]:
        out: list[AgentEvent] = []
        async for event in events:
            out.append(event)
        return out

    return asyncio.run(_collect())


# --- 1. InvocationCompleted produces a runs row with all 15 fields ---


def test_invocation_completed_writes_run_record_with_final_result() -> None:
    template = _agent_template()
    revision = _agent_revision(template.id)
    repository = _FakeAgentRepository(template, revision)
    writer = _FakeRunHistoryWriter()
    executor = _ScriptedExecutor([
        _start_event(template.id),
        _iter_started(1),
        ContentDelta(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            text_fragment="The framed problem is...",
        ),
        _iter_completed(1, Decimal("0.0005")),
        InvocationCompleted(
            invocation_id=_INVOCATION_ID,
            final_result="The framed problem is X.",
            termination_reason=TerminationReason.CONTENT,
            total_cost_usd=Decimal("0.0005"),
            audit_chain_hashes=(_START_HASH, _END_HASH),
            duration_ms=100,
        ),
    ])

    _drive(invoke_agent(
        principal=_operator_principal(),
        repository=repository,
        role_lookup=_NoopRoleLookup(),
        methodology_overrides_lookup=_NoopOverridesLookup(),
        tool_definitions_lookup=_empty_tool_definitions_lookup,
        executor=executor,
        writer=writer,
        security_events=_FakeSecurityEventLogger(),
        tenant_context=_tenant_context(),
        agent_template_id=template.id,
        user_input="frame the problem",
    ))

    assert len(writer.calls) == 1
    record = writer.calls[0]
    assert record.id == _INVOCATION_ID
    assert record.tenant_id == _TENANT_A
    assert record.jurisdiction == "eu-west"
    assert record.agent_template_id == template.id
    assert record.agent_template_version == revision.version
    assert record.input_message == "frame the problem"
    assert record.output_content == "The framed problem is X."
    assert record.termination_reason == "content"
    assert record.iteration_count == 1
    assert record.total_cost_usd == Decimal("0.0005")
    assert record.audit_start_hash == _START_HASH
    assert record.audit_end_hash == _END_HASH
    assert record.trace_id is None  # OTel integration deferred


# --- 2. InvariantBlocked produces a runs row with synthesised reason ---


def test_invariant_blocked_writes_run_record_with_synthesised_reason() -> None:
    template = _agent_template()
    revision = _agent_revision(template.id)
    repository = _FakeAgentRepository(template, revision)
    writer = _FakeRunHistoryWriter()
    executor = _ScriptedExecutor([
        _start_event(template.id),
        _iter_started(1),
        _iter_completed(1, Decimal("0.0003")),
        InvariantBlocked(
            invocation_id=_INVOCATION_ID,
            classification="financial",
            blocked_tool_name="charge_card",
            audit_chain_hashes=(_START_HASH, _END_HASH),
        ),
    ])

    _drive(invoke_agent(
        principal=_operator_principal(),
        repository=repository,
        role_lookup=_NoopRoleLookup(),
        methodology_overrides_lookup=_NoopOverridesLookup(),
        tool_definitions_lookup=_empty_tool_definitions_lookup,
        executor=executor,
        writer=writer,
        security_events=_FakeSecurityEventLogger(),
        tenant_context=_tenant_context(),
        agent_template_id=template.id,
        user_input="pay me",
    ))

    assert len(writer.calls) == 1
    record = writer.calls[0]
    assert record.termination_reason == "invariant_blocked"
    assert record.audit_start_hash == _START_HASH
    assert record.audit_end_hash == _END_HASH
    assert record.output_content == ""
    assert record.total_cost_usd == Decimal("0.0003")  # accumulated


# --- 3. InvocationFailed with 1-hash partial state ---


def test_invocation_failed_one_hash_writes_with_null_end_hash() -> None:
    """1-hash case: loop-body exception or end-audit emission failure.
    Runs row exists with audit_end_hash=NULL and termination_reason='failed'.
    """
    template = _agent_template()
    revision = _agent_revision(template.id)
    repository = _FakeAgentRepository(template, revision)
    writer = _FakeRunHistoryWriter()
    executor = _ScriptedExecutor([
        _start_event(template.id),
        _iter_started(1),
        _iter_completed(1, Decimal("0.0001")),
        InvocationFailed(
            invocation_id=_INVOCATION_ID,
            error_type="RuntimeError",
            error_detail="upstream timeout",
            partial_audit_chain_state=(_START_HASH,),
            duration_ms=200,
        ),
    ])

    _drive(invoke_agent(
        principal=_operator_principal(),
        repository=repository,
        role_lookup=_NoopRoleLookup(),
        methodology_overrides_lookup=_NoopOverridesLookup(),
        tool_definitions_lookup=_empty_tool_definitions_lookup,
        executor=executor,
        writer=writer,
        security_events=_FakeSecurityEventLogger(),
        tenant_context=_tenant_context(),
        agent_template_id=template.id,
        user_input="frame the problem",
    ))

    assert len(writer.calls) == 1
    record = writer.calls[0]
    assert record.termination_reason == "failed"
    assert record.audit_start_hash == _START_HASH
    assert record.audit_end_hash is None
    assert record.output_content == ""
    assert record.total_cost_usd == Decimal("0.0001")


def test_invocation_failed_two_hash_writes_with_both_hashes() -> None:
    """2-hash forward-affordance variant: runs row with both hashes
    and termination_reason='failed'. Not currently fired by the
    executor but the assembly seam handles it per D95."""
    template = _agent_template()
    revision = _agent_revision(template.id)
    repository = _FakeAgentRepository(template, revision)
    writer = _FakeRunHistoryWriter()
    executor = _ScriptedExecutor([
        _start_event(template.id),
        InvocationFailed(
            invocation_id=_INVOCATION_ID,
            error_type="PostEndAuditError",
            error_detail="forward-affordance variant",
            partial_audit_chain_state=(_START_HASH, _END_HASH),
            duration_ms=200,
        ),
    ])

    _drive(invoke_agent(
        principal=_operator_principal(),
        repository=repository,
        role_lookup=_NoopRoleLookup(),
        methodology_overrides_lookup=_NoopOverridesLookup(),
        tool_definitions_lookup=_empty_tool_definitions_lookup,
        executor=executor,
        writer=writer,
        security_events=_FakeSecurityEventLogger(),
        tenant_context=_tenant_context(),
        agent_template_id=template.id,
        user_input="frame the problem",
    ))

    assert len(writer.calls) == 1
    record = writer.calls[0]
    assert record.termination_reason == "failed"
    assert record.audit_start_hash == _START_HASH
    assert record.audit_end_hash == _END_HASH


# --- 4. InvocationFailed with 0-hash → no runs row ---


def test_invocation_failed_zero_hash_skips_writer() -> None:
    """Pre-start-audit failure: no audit evidence, no projection target,
    no runs row per D95's projection-over-recorded-activity framing."""
    template = _agent_template()
    revision = _agent_revision(template.id)
    repository = _FakeAgentRepository(template, revision)
    writer = _FakeRunHistoryWriter()
    executor = _ScriptedExecutor([
        _start_event(template.id),
        InvocationFailed(
            invocation_id=_INVOCATION_ID,
            error_type="PreStartAuditError",
            error_detail="start audit emission failed",
            partial_audit_chain_state=(),
            duration_ms=10,
        ),
    ])

    _drive(invoke_agent(
        principal=_operator_principal(),
        repository=repository,
        role_lookup=_NoopRoleLookup(),
        methodology_overrides_lookup=_NoopOverridesLookup(),
        tool_definitions_lookup=_empty_tool_definitions_lookup,
        executor=executor,
        writer=writer,
        security_events=_FakeSecurityEventLogger(),
        tenant_context=_tenant_context(),
        agent_template_id=template.id,
        user_input="frame the problem",
    ))

    assert writer.calls == []


# --- 5. Auth-failure → no writer call ---


def test_auth_failure_skips_writer() -> None:
    """Auth check fires at first __anext__ before any event yields;
    writer is never called. The auth-failed path produces no audit
    row and no runs row."""
    template = _agent_template()
    revision = _agent_revision(template.id)
    repository = _FakeAgentRepository(template, revision)
    writer = _FakeRunHistoryWriter()
    executor = _ScriptedExecutor([])

    with pytest.raises(AuthorizationError):
        _drive(invoke_agent(
            principal=_unauth_principal(),
            repository=repository,
            role_lookup=_NoopRoleLookup(),
            methodology_overrides_lookup=_NoopOverridesLookup(),
            tool_definitions_lookup=_empty_tool_definitions_lookup,
            executor=executor,
            writer=writer,
            security_events=_FakeSecurityEventLogger(),
            tenant_context=_tenant_context(),
            agent_template_id=template.id,
            user_input="frame the problem",
        ))

    assert writer.calls == []


# --- 6. Ordering: terminal event yielded BEFORE writer.record_run ---


def test_terminal_event_yields_before_writer_called() -> None:
    """D95 shape B: yield terminal event first, then write, then return.
    A shared ordering log captures the sequence. The terminal event
    is delivered to the consumer; the writer call follows."""
    template = _agent_template()
    revision = _agent_revision(template.id)
    repository = _FakeAgentRepository(template, revision)

    ordering: list[str] = []
    writer = _FakeRunHistoryWriter(ordering_log=ordering)

    executor = _ScriptedExecutor([
        _start_event(template.id),
        InvocationCompleted(
            invocation_id=_INVOCATION_ID,
            final_result="ok",
            termination_reason=TerminationReason.CONTENT,
            total_cost_usd=Decimal("0.0001"),
            audit_chain_hashes=(_START_HASH, _END_HASH),
            duration_ms=100,
        ),
    ])

    async def _consumer() -> None:
        async for event in invoke_agent(
            principal=_operator_principal(),
            repository=repository,
            role_lookup=_NoopRoleLookup(),
            methodology_overrides_lookup=_NoopOverridesLookup(),
            tool_definitions_lookup=_empty_tool_definitions_lookup,
            executor=executor,
            writer=writer,
            security_events=_FakeSecurityEventLogger(),
            tenant_context=_tenant_context(),
            agent_template_id=template.id,
            user_input="frame the problem",
        ):
            if isinstance(event, InvocationCompleted):
                ordering.append("consumer:InvocationCompleted")

    asyncio.run(_consumer())

    # Terminal event reaches the consumer before the writer call.
    assert ordering == ["consumer:InvocationCompleted", "writer.record_run"]
