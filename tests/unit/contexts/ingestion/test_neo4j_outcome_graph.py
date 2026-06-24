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
        "aliases": None,
        "domain": None,
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


# --- Archive / re-activate (S103e, D205): reversible, non-destructive ---------


def test_list_outcomes_scopes_to_active_goals() -> None:
    # The list Cypher carries the archive filter, so an archived goal (one that
    # carries o.archived_at) drops out of every consumer that reads list_goals —
    # the assess surface and the matcher — without being deleted.
    driver, session = _mock_driver()
    result = MagicMock()
    result.data = AsyncMock(return_value=[])
    session.run = AsyncMock(return_value=result)

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            await s.list_outcomes()

    asyncio.run(run())
    cypher = session.run.call_args.args[0]
    assert re.search(r"o\.archived_at\s+IS\s+NULL", cypher), cypher


def test_archive_outcome_sets_marker_and_binds_tenant() -> None:
    driver, session = _mock_driver()
    result = MagicMock()
    result.single = AsyncMock(return_value={"outcome_id": str(_OUTCOME_ID)})
    session.run = AsyncMock(return_value=result)

    async def run() -> bool:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            return await s.archive_outcome(outcome_id=_OUTCOME_ID)

    found = asyncio.run(run())
    assert found is True
    cypher, params = session.run.call_args.args[0], session.run.call_args.args[1]
    # Sets the marker (not a delete) and binds the tenant predicate.
    assert "SET o.archived_at" in cypher
    assert "DELETE" not in cypher.upper() and "REMOVE" not in cypher
    assert params["tenant_id"] == _TENANT.tenant_id
    assert params["outcome_id"] == str(_OUTCOME_ID)
    assert params["archived_at"] is not None


def test_archive_outcome_missing_returns_false() -> None:
    driver, session = _mock_driver()
    result = MagicMock()
    result.single = AsyncMock(return_value=None)
    session.run = AsyncMock(return_value=result)

    async def run() -> bool:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            return await s.archive_outcome(outcome_id=_OUTCOME_ID)

    assert asyncio.run(run()) is False


def test_unarchive_outcome_removes_marker() -> None:
    driver, session = _mock_driver()
    result = MagicMock()
    result.single = AsyncMock(return_value={"outcome_id": str(_OUTCOME_ID)})
    session.run = AsyncMock(return_value=result)

    async def run() -> bool:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            return await s.unarchive_outcome(outcome_id=_OUTCOME_ID)

    found = asyncio.run(run())
    assert found is True
    cypher = session.run.call_args.args[0]
    # Re-activation removes the marker (returns the goal whole); never deletes.
    assert "REMOVE o.archived_at" in cypher
    assert "DELETE" not in cypher.upper()


def test_list_archived_outcome_ids_filters_to_archived() -> None:
    driver, session = _mock_driver()
    result = MagicMock()
    result.data = AsyncMock(return_value=[{"outcome_id": str(_OUTCOME_ID)}])
    session.run = AsyncMock(return_value=result)

    async def run() -> list:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            return await s.list_archived_outcome_ids()

    ids = asyncio.run(run())
    assert ids == [_OUTCOME_ID]
    cypher, params = session.run.call_args.args[0], session.run.call_args.args[1]
    assert re.search(r"o\.archived_at\s+IS\s+NOT\s+NULL", cypher), cypher
    assert params["tenant_id"] == _TENANT.tenant_id


# --- Process gates (S103g, D207) ---------------------------------------------

_GATE_ID = UUID("00000000-0000-4000-8000-0000063a0001")


def test_merge_gate_binds_tenant_and_fields() -> None:
    driver, session = _mock_driver()

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            await s.merge_gate(
                gate_id=_GATE_ID, outcome_id=_OUTCOME_ID, name="Apply",
                gate_order=3, local_outcome="Expected interviews generated",
                local_goal="highest return on marginal effort",
                provenance_origin="llm_drafted", proof_state="pending",
                step_commitment_id=_COMMITMENT_ID,
            )

    asyncio.run(run())
    cypher, params = session.run.call_args.args[0], session.run.call_args.args[1]
    assert "MERGE (g:Gate" in cypher
    assert params["tenant_id"] == _TENANT.tenant_id
    assert params["gate_id"] == str(_GATE_ID)
    assert params["name"] == "Apply"
    assert params["gate_order"] == 3
    assert params["step_commitment_id"] == str(_COMMITMENT_ID)


def test_merge_authored_element_carries_gate_id() -> None:
    driver, session = _mock_driver()

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            await s.merge_authored_element(
                outcome_id=_OUTCOME_ID, element_kind="intermediary",
                element_id=_OUTCOME_ID, label="Screen-through probability",
                provenance_origin="llm_drafted", proof_state="pending",
                gate_id=_GATE_ID,
            )

    asyncio.run(run())
    cypher, params = session.run.call_args.args[0], session.run.call_args.args[1]
    assert "n.gate_id = $gate_id" in cypher
    assert params["gate_id"] == str(_GATE_ID)


def test_merge_authored_element_goal_level_gate_id_none() -> None:
    driver, session = _mock_driver()

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            await s.merge_authored_element(
                outcome_id=_OUTCOME_ID, element_kind="lever",
                element_id=_OUTCOME_ID, label="Origination",
                provenance_origin="llm_drafted", proof_state="pending",
            )

    asyncio.run(run())
    params = session.run.call_args.args[1]
    assert params["gate_id"] is None


def test_set_element_gate_runs_relocation_cypher() -> None:
    driver, session = _mock_driver()
    result = MagicMock()
    result.single = AsyncMock(return_value={"element_id": str(_OUTCOME_ID)})
    session.run = AsyncMock(return_value=result)

    async def run() -> bool:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            return await s.set_element_gate(
                element_kind="lever", element_id=_OUTCOME_ID, gate_id=_GATE_ID
            )

    ok = asyncio.run(run())
    assert ok is True
    cypher, params = session.run.call_args.args[0], session.run.call_args.args[1]
    assert "SET n.gate_id = $gate_id" in cypher
    # relocation preserves provenance — it must NOT set provenance_origin.
    assert "provenance_origin" not in cypher
    assert params["gate_id"] == str(_GATE_ID)


def test_delete_authored_edge_targets_the_endpoints() -> None:
    driver, session = _mock_driver()

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            await s.delete_authored_edge(
                edge_type="FEEDS", source_kind="lever", source_id=_OUTCOME_ID,
                target_kind="intermediary", target_id=_COMMITMENT_ID,
            )

    asyncio.run(run())
    cypher = session.run.call_args.args[0]
    assert "DELETE r" in cypher
    assert ":Lever" in cypher and ":Intermediary" in cypher


# --- Process instances / opportunities (S103h, D208) -------------------------

_OPP_ID = UUID("00000000-0000-4000-8000-0000063b0001")


def test_merge_opportunity_binds_tenant_and_fields() -> None:
    driver, session = _mock_driver()

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            await s.merge_opportunity(
                opportunity_id=_OPP_ID, outcome_id=_OUTCOME_ID, name="Acme",
                current_gate_id=_GATE_ID, provenance_origin="system_suggested",
                proof_state="pending", source="acme.example",
            )

    asyncio.run(run())
    cypher, params = session.run.call_args.args[0], session.run.call_args.args[1]
    assert "MERGE (o:Opportunity" in cypher
    assert params["opportunity_id"] == str(_OPP_ID)
    assert params["name"] == "Acme"
    assert params["current_gate_id"] == str(_GATE_ID)
    assert params["provenance_origin"] == "system_suggested"


def test_attach_unit_to_opportunity_merges_belongs_to() -> None:
    driver, session = _mock_driver()

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            await s.attach_unit_to_opportunity(
                unit_id=_OUTCOME_ID, opportunity_id=_OPP_ID
            )

    asyncio.run(run())
    cypher = session.run.call_args.args[0]
    assert "MERGE (u)-[r:BELONGS_TO" in cypher


def test_element_evidence_read_scopes_to_opportunity() -> None:
    # The evidence read OPTIONAL-MATCHes the unit's BELONGS_TO so a clustered
    # unit's gate binds carry its opportunity (D208).
    driver, session = _mock_driver()
    result = MagicMock()
    result.data = AsyncMock(return_value=[])
    session.run = AsyncMock(return_value=result)

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            await s.list_element_evidence()

    asyncio.run(run())
    cypher = session.run.call_args.args[0]
    assert "BELONGS_TO" in cypher and "opportunity_id" in cypher
