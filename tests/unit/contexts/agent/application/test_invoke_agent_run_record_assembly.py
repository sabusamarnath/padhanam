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
    assert record.trace_id is None  # no active OTel span scope in unit test


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


# ---------------------------------------------------------------------------
# D96 / S32: citation accumulator + within-run deduplication
# ---------------------------------------------------------------------------


def _chunk_candidate(*, chunk_id: UUID, content: str = "content"):
    from contexts.agent.domain.citation_candidates import ChunkCitationCandidate

    return ChunkCitationCandidate(
        chunk_id=chunk_id,
        source_id=UUID(int=99),
        chunk_index=0,
        content_snapshot=content,
        source_snapshot={"file_name": "doc.pdf", "file_type": "application/pdf"},
        tenant_id=_TENANT_A,
        jurisdiction="eu-west",
    )


def _entity_candidate(*, name: str, etype: str = "Organization"):
    from contexts.agent.domain.citation_candidates import EntityCitationCandidate

    return EntityCitationCandidate(
        entity_tenant_id=_TENANT_A,
        entity_name=name,
        entity_type=etype,
        source_chunk_ids=(UUID(int=10),),
        tenant_id=_TENANT_A,
        jurisdiction="eu-west",
    )


def _tool_completed(*, idx: int, candidates: tuple = ()):
    from contexts.agent.domain.events import ToolCallCompleted

    return ToolCallCompleted(
        invocation_id=_INVOCATION_ID,
        iteration_index=idx,
        tool_name="retrieval",
        success=True,
        result_summary="ok",
        duration_ms=10,
        citation_candidates=candidates,
    )


def test_invoke_agent_accumulator_passes_citations_to_writer() -> None:
    """D96: a single ToolCallCompleted with three chunk candidates
    produces three rows in writer.record_run's chunk_citations."""
    template = _agent_template()
    revision = _agent_revision(template.id)
    repository = _FakeAgentRepository(template, revision)
    writer = _FakeRunHistoryWriter()
    chunk_a = _chunk_candidate(chunk_id=UUID(int=1), content="A")
    chunk_b = _chunk_candidate(chunk_id=UUID(int=2), content="B")
    chunk_c = _chunk_candidate(chunk_id=UUID(int=3), content="C")
    executor = _ScriptedExecutor([
        _start_event(template.id),
        _iter_started(1),
        _tool_completed(idx=1, candidates=(chunk_a, chunk_b, chunk_c)),
        _iter_completed(1, Decimal("0.001")),
        InvocationCompleted(
            invocation_id=_INVOCATION_ID,
            final_result="ok",
            termination_reason=TerminationReason.CONTENT,
            total_cost_usd=Decimal("0.001"),
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
        user_input="q",
    ))

    assert len(writer.calls) == 1
    record = writer.calls[0]
    assert len(record.chunk_citations) == 3
    assert record.chunk_citations[0] is chunk_a
    assert record.chunk_citations[1] is chunk_b
    assert record.chunk_citations[2] is chunk_c
    assert record.entity_citations == ()


def test_invoke_agent_accumulator_deduplicates_chunks_within_run() -> None:
    """D96: a chunk retrieved by two ToolCallCompleted events within
    the same run produces one row; first-seen-wins."""
    template = _agent_template()
    revision = _agent_revision(template.id)
    repository = _FakeAgentRepository(template, revision)
    writer = _FakeRunHistoryWriter()
    shared_id = UUID(int=42)
    first_seen = _chunk_candidate(chunk_id=shared_id, content="FIRST")
    second_seen = _chunk_candidate(chunk_id=shared_id, content="SECOND")
    executor = _ScriptedExecutor([
        _start_event(template.id),
        _iter_started(1),
        _tool_completed(idx=1, candidates=(first_seen,)),
        _iter_completed(1, Decimal("0.001")),
        _iter_started(2),
        _tool_completed(idx=2, candidates=(second_seen,)),
        _iter_completed(2, Decimal("0.001")),
        InvocationCompleted(
            invocation_id=_INVOCATION_ID,
            final_result="ok",
            termination_reason=TerminationReason.CONTENT,
            total_cost_usd=Decimal("0.002"),
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
        user_input="q",
    ))

    record = writer.calls[0]
    assert len(record.chunk_citations) == 1
    # First-seen wins: the FIRST snapshot persisted, not the SECOND.
    assert record.chunk_citations[0].content_snapshot == "FIRST"


def test_invoke_agent_accumulator_deduplicates_entities_by_composite_key() -> None:
    """D96: entity dedup keys on (entity_tenant_id, entity_name,
    entity_type); same composite seen twice yields one row."""
    template = _agent_template()
    revision = _agent_revision(template.id)
    repository = _FakeAgentRepository(template, revision)
    writer = _FakeRunHistoryWriter()
    acme_v1 = _entity_candidate(name="Acme")
    acme_v2 = _entity_candidate(name="Acme")  # same composite key
    different = _entity_candidate(name="Acme", etype="Person")  # different etype
    executor = _ScriptedExecutor([
        _start_event(template.id),
        _iter_started(1),
        _tool_completed(idx=1, candidates=(acme_v1, acme_v2, different)),
        _iter_completed(1, Decimal("0.001")),
        InvocationCompleted(
            invocation_id=_INVOCATION_ID,
            final_result="ok",
            termination_reason=TerminationReason.CONTENT,
            total_cost_usd=Decimal("0.001"),
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
        user_input="q",
    ))

    record = writer.calls[0]
    # The (Acme, Organization) composite collapses to one; (Acme, Person)
    # is a distinct composite so it lands as a second row.
    assert len(record.entity_citations) == 2
    assert record.entity_citations[0].entity_name == "Acme"
    assert record.entity_citations[0].entity_type == "Organization"
    assert record.entity_citations[1].entity_type == "Person"


def test_invoke_agent_accumulator_passes_chunks_and_entities_together() -> None:
    """D96: mixed candidates split correctly between the two
    accumulator surfaces."""
    template = _agent_template()
    revision = _agent_revision(template.id)
    repository = _FakeAgentRepository(template, revision)
    writer = _FakeRunHistoryWriter()
    chunk = _chunk_candidate(chunk_id=UUID(int=1))
    entity = _entity_candidate(name="Acme")
    executor = _ScriptedExecutor([
        _start_event(template.id),
        _iter_started(1),
        _tool_completed(idx=1, candidates=(chunk, entity)),
        _iter_completed(1, Decimal("0.001")),
        InvocationCompleted(
            invocation_id=_INVOCATION_ID,
            final_result="ok",
            termination_reason=TerminationReason.CONTENT,
            total_cost_usd=Decimal("0.001"),
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
        user_input="q",
    ))

    record = writer.calls[0]
    assert len(record.chunk_citations) == 1
    assert len(record.entity_citations) == 1
    assert record.chunk_citations[0] is chunk
    assert record.entity_citations[0] is entity


def test_invoke_agent_no_tool_calls_yields_empty_citation_lists() -> None:
    """D96: a content-only invocation (no ToolCallCompleted events)
    produces empty citation tuples on the run record."""
    template = _agent_template()
    revision = _agent_revision(template.id)
    repository = _FakeAgentRepository(template, revision)
    writer = _FakeRunHistoryWriter()
    executor = _ScriptedExecutor([
        _start_event(template.id),
        _iter_started(1),
        _iter_completed(1, Decimal("0.0005")),
        InvocationCompleted(
            invocation_id=_INVOCATION_ID,
            final_result="ok",
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
        user_input="q",
    ))

    record = writer.calls[0]
    assert record.chunk_citations == ()
    assert record.entity_citations == ()
