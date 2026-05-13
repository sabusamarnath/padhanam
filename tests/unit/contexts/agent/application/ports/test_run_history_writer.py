"""Unit tests for RunHistoryWriter port and AgentRunRecord DTO (D17, D95, S31).

Three concerns mirror test_role_lookup.py and test_methodology_lookup.py:

1. AgentRunRecord is a frozen dataclass with the 15-field D95 set.
2. RunHistoryWriter is a Protocol; an async callable with the
   right method signature satisfies it structurally without
   explicit inheritance.
3. The module imports nothing from ``contexts.run_history`` —
   the consumer-side DTO pattern from D17 / D5 / D79 extends to
   the new writer port to preserve cross-context independence;
   the AST parse surfaces accidental import drift before
   import-linter does.
"""

from __future__ import annotations

import ast
import asyncio
from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from contexts.agent.application.ports.run_history_writer import (
    AgentRunRecord,
    RunHistoryWriter,
)
from padhanam.security import OPERATOR_ROLE, Principal
from shared_kernel import TenantId


_D95_FIELD_NAMES = {
    "id",
    "tenant_id",
    "jurisdiction",
    "agent_template_id",
    "agent_template_version",
    "input_message",
    "output_content",
    "started_at",
    "completed_at",
    "termination_reason",
    "iteration_count",
    "total_cost_usd",
    "trace_id",
    "audit_start_hash",
    "audit_end_hash",
    "created_at",
}


def _make_record(**overrides) -> AgentRunRecord:
    defaults = dict(
        id=uuid4(),
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        agent_template_id=uuid4(),
        agent_template_version=1,
        input_message="hello",
        output_content="hi back",
        started_at=datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 5, 13, 12, 1, 0, tzinfo=timezone.utc),
        termination_reason="content",
        iteration_count=1,
        total_cost_usd=Decimal("0.001"),
        trace_id=None,
        audit_start_hash="0" * 64,
        audit_end_hash="1" * 64,
        created_at=datetime(2026, 5, 13, 12, 1, 5, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return AgentRunRecord(**defaults)


def test_agent_run_record_is_frozen_dataclass() -> None:
    assert is_dataclass(AgentRunRecord)
    record = _make_record()
    with pytest.raises(FrozenInstanceError):
        record.tenant_id = "tenant-b"  # type: ignore[misc]


def test_agent_run_record_field_set_matches_d95() -> None:
    actual = {f.name for f in fields(AgentRunRecord)}
    assert actual == _D95_FIELD_NAMES, (
        f"AgentRunRecord fields drifted from D95: "
        f"unexpected={actual - _D95_FIELD_NAMES}, "
        f"missing={_D95_FIELD_NAMES - actual}"
    )


def test_agent_run_record_carries_no_invariants() -> None:
    """The DTO is a pure data carrier; validation is the producer-
    side domain object's responsibility per D17. Constructing with
    an empty tenant_id must not raise from the DTO layer (the
    domain object on the producer side will reject it)."""
    record = _make_record(tenant_id="")
    assert record.tenant_id == ""


def test_run_history_writer_is_structurally_satisfiable() -> None:
    """Protocol satisfaction is structural; an async method named
    ``record_run`` taking ``(record, *, principal)`` satisfies the
    type without explicit inheritance."""
    captured: list[AgentRunRecord] = []

    class _FakeWriter:
        async def record_run(
            self,
            record: AgentRunRecord,
            *,
            principal: Principal,
        ) -> None:
            captured.append(record)

    writer: RunHistoryWriter = _FakeWriter()  # type: ignore[assignment]
    principal = Principal(
        subject="alice",
        tenant_id=TenantId("tenant-a"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="x",
    )
    record = _make_record()
    asyncio.run(writer.record_run(record, principal=principal))
    assert captured == [record]


def test_run_history_writer_module_imports_nothing_from_run_history() -> None:
    """D17 cross-context independence at the file level: the
    writer port module must not import from contexts.run_history.
    AST backstop for the import-linter contract."""
    module_path = Path(
        "/Users/sabu/padhanam/contexts/agent/application/ports/"
        "run_history_writer.py"
    )
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_prefixes = (
        "contexts.run_history",
        "contexts.methodology",
        "contexts.ingestion",
        "contexts.tools",
    )
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(forbidden_prefixes):
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith(forbidden_prefixes):
                offenders.append(mod)
    assert offenders == [], (
        f"run_history_writer.py imports from forbidden cross-context "
        f"modules: {offenders}"
    )
