"""Unit tests for the goal-graph methods on TenantScopedNeo4jSession (S62, D163).

The Outcome node + lever-to-outcome edge are a new typed capability on the same
single Cypher surface (the wrapper), so these tests mirror the entity-graph
wrapper tests: the AsyncDriver/AsyncSession are mocked, and the tests assert the
Cypher params auto-bind the bound tenant_id + jurisdiction and that reads map
the driver rows onto ``OutcomeGraphRecord``.
"""

from __future__ import annotations

import asyncio
import re
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from contexts.ingestion.adapters.outbound.neo4j.session import (
    TenantScopedNeo4jSession,
)
from contexts.ingestion.ports.outcome_graph_port import OutcomeGraphRecord
from shared_kernel import TenantContext

_TENANT = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000d001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000d001",
)

_OUTCOME_ID = UUID("00000000-0000-4000-8000-0000000000a1")
_COMMITMENT_ID = UUID("00000000-0000-4000-8000-0000000000b2")


def _mock_driver() -> tuple[MagicMock, MagicMock]:
    session = MagicMock()
    session.run = AsyncMock()
    session.close = AsyncMock()
    driver = MagicMock()
    driver.session = MagicMock(return_value=session)
    return driver, session


def test_merge_outcome_binds_tenant_and_fields() -> None:
    driver, session = _mock_driver()

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            await s.merge_outcome(
                outcome_id=_OUTCOME_ID,
                name="German",
                control="self",
                subject="self",
                mode="progressive",
                ladder=("A1", "A2", "B1"),
                current_target_level="A2",
            )

    asyncio.run(run())
    cypher, params = session.run.call_args.args[0], session.run.call_args.args[1]
    assert params["tenant_id"] == _TENANT.tenant_id
    assert params["jurisdiction"] == "eu-west"
    assert params["outcome_id"] == str(_OUTCOME_ID)
    assert params["name"] == "German"
    assert params["control"] == "self"
    assert params["subject"] == "self"
    # Goal-level properties now live on the node (D163 clarification, S63).
    assert params["mode"] == "progressive"
    assert params["ladder"] == ["A1", "A2", "B1"]
    assert params["current_target_level"] == "A2"
    # Every $placeholder in the Cypher must be supplied — live Neo4j rejects a
    # missing parameter (the created_at miss the S62 live smoke caught; the
    # mock session.run does not validate, so assert the contract here).
    placeholders = set(re.findall(r"\$(\w+)", cypher))
    assert placeholders <= set(params), placeholders - set(params)


def test_merge_lever_for_outcome_carries_only_the_relationship() -> None:
    driver, session = _mock_driver()

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            await s.merge_lever_for_outcome(
                outcome_id=_OUTCOME_ID,
                commitment_id=_COMMITMENT_ID,
            )

    asyncio.run(run())
    cypher, params = session.run.call_args.args[0], session.run.call_args.args[1]
    assert params["tenant_id"] == _TENANT.tenant_id
    assert params["commitment_id"] == str(_COMMITMENT_ID)
    # The edge no longer carries goal-level properties (D163 clarification).
    assert "mode" not in params
    assert "ladder" not in params
    assert "current_target_level" not in params
    assert "$mode" not in cypher and "$current_target_level" not in cypher
    placeholders = set(re.findall(r"\$(\w+)", cypher))
    assert placeholders <= set(params), placeholders - set(params)


def test_set_outcome_target_returns_new_level() -> None:
    driver, session = _mock_driver()
    result = MagicMock()
    result.single = AsyncMock(return_value={"current_target_level": "B1"})
    session.run = AsyncMock(return_value=result)

    async def run() -> str | None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            return await s.set_outcome_target(
                outcome_id=_OUTCOME_ID,
                current_target_level="B1",
            )

    assert asyncio.run(run()) == "B1"


def test_set_outcome_target_missing_outcome_returns_none() -> None:
    driver, session = _mock_driver()
    result = MagicMock()
    result.single = AsyncMock(return_value=None)
    session.run = AsyncMock(return_value=result)

    async def run() -> str | None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            return await s.set_outcome_target(
                outcome_id=_OUTCOME_ID,
                current_target_level="B1",
            )

    assert asyncio.run(run()) is None


def _row(**overrides) -> dict:
    base = {
        "outcome_id": str(_OUTCOME_ID),
        "name": "German",
        "control": "self",
        "subject": "self",
        "mode": "progressive",
        "ladder": ["A1", "A2", "B1"],
        "current_target_level": "A2",
        "terminal_target": None,
        "terminal_state": None,
        "commitment_id": str(_COMMITMENT_ID),
        "step_order": None,
        "step_state": None,
    }
    base.update(overrides)
    return base


def test_list_outcomes_maps_progressive_single_lever() -> None:
    driver, session = _mock_driver()
    result = MagicMock()
    result.data = AsyncMock(return_value=[_row()])
    session.run = AsyncMock(return_value=result)

    async def run() -> list[OutcomeGraphRecord]:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            return list(await s.list_outcomes())

    records = asyncio.run(run())
    assert len(records) == 1
    rec = records[0]
    assert rec.mode == "progressive"
    assert rec.ladder == ("A1", "A2", "B1")
    assert rec.current_target_level == "A2"
    assert rec.terminal_target is None
    assert len(rec.levers) == 1
    assert rec.levers[0].commitment_id == _COMMITMENT_ID
    assert rec.levers[0].step_order is None


def test_list_outcomes_aggregates_sequence_lever_chain() -> None:
    driver, session = _mock_driver()
    seq_outcome = UUID("00000000-0000-4000-8000-0000006300a1")
    c1 = UUID("00000000-0000-4000-8000-0000006300c1")
    c2 = UUID("00000000-0000-4000-8000-0000006300c2")
    result = MagicMock()
    result.data = AsyncMock(
        return_value=[
            _row(
                outcome_id=str(seq_outcome),
                name="Get a job",
                control="other",
                subject="self",
                mode="sequence",
                ladder=None,
                current_target_level=None,
                terminal_target="Offer accepted",
                terminal_state="pending",
                commitment_id=str(c1),
                step_order=1,
                step_state="done",
            ),
            _row(
                outcome_id=str(seq_outcome),
                name="Get a job",
                control="other",
                subject="self",
                mode="sequence",
                ladder=None,
                current_target_level=None,
                terminal_target="Offer accepted",
                terminal_state="pending",
                commitment_id=str(c2),
                step_order=2,
                step_state="blocked",
            ),
        ]
    )
    session.run = AsyncMock(return_value=result)

    async def run() -> list[OutcomeGraphRecord]:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            return list(await s.list_outcomes())

    records = asyncio.run(run())
    # Two rows, one outcome → one aggregated record with a two-step chain.
    assert len(records) == 1
    rec = records[0]
    assert rec.mode == "sequence"
    assert rec.terminal_target == "Offer accepted"
    assert rec.terminal_state == "pending"
    assert len(rec.levers) == 2
    assert rec.levers[0].commitment_id == c1
    assert rec.levers[0].step_order == 1
    assert rec.levers[0].step_state == "done"
    assert rec.levers[1].step_order == 2
    assert rec.levers[1].step_state == "blocked"
