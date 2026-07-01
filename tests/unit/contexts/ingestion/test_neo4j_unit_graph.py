"""Unit tests for the work-unit-graph methods on TenantScopedNeo4jSession (S66, D168).

The :Unit / :Facet / SAME_WORK shape is a new typed capability on the same single
Cypher surface (the wrapper), so these tests mirror the outcome-graph wrapper
tests: the AsyncDriver/AsyncSession are mocked, the tests assert the Cypher params
auto-bind the bound tenant_id + jurisdiction, that every $placeholder is supplied
(the S62 live-smoke parameter-contract lesson), and that reads aggregate the
driver rows onto ``UnitGraphRecord``.
"""

from __future__ import annotations

import asyncio
import re
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from contexts.ingestion.adapters.outbound.neo4j.session import (
    TenantScopedNeo4jSession,
)
from contexts.ingestion.ports.unit_graph_port import (
    FacetLinkWrite,
    GoalEdgeWrite,
    UnitGraphRecord,
    UnitWrite,
)
from shared_kernel import TenantContext

_TENANT = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000d001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000d001",
)

_UNIT_ID = UUID("00000000-0000-4000-8000-0000006600a1")
_TASK_ID = UUID("00000000-0000-4000-8000-0000006600b1")
_MEETING_ID = UUID("00000000-0000-4000-8000-0000006600b2")


def _mock_driver() -> tuple[MagicMock, MagicMock]:
    session = MagicMock()
    session.run = AsyncMock()
    session.close = AsyncMock()
    driver = MagicMock()
    driver.session = MagicMock(return_value=session)
    return driver, session


def _all_calls(session: MagicMock) -> list[tuple[str, dict]]:
    return [(c.args[0], c.args[1]) for c in session.run.call_args_list]


def test_replace_units_deletes_prunes_and_merges_with_bound_tenant() -> None:
    driver, session = _mock_driver()
    unit = UnitWrite(
        unit_id=_UNIT_ID,
        links=(
            FacetLinkWrite(
                facet_type="task",
                facet_id=_TASK_ID,
                confidence=1.0,
                status="confirmed",
                basis="anchor",
            ),
            FacetLinkWrite(
                facet_type="meeting",
                facet_id=_MEETING_ID,
                confidence=0.9,
                status="confirmed",
                basis="title+time",
            ),
        ),
    )

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            await s.replace_units([unit])

    asyncio.run(run())
    calls = _all_calls(session)
    # delete facets, prune units, merge the unit, link two facets = 5 runs.
    assert len(calls) == 5

    # Every statement binds the bound tenant and supplies every $placeholder.
    for cypher, params in calls:
        assert params["tenant_id"] == _TENANT.tenant_id
        placeholders = set(re.findall(r"\$(\w+)", cypher))
        assert placeholders <= set(params), (cypher, placeholders - set(params))

    # The prune keeps exactly the recomputed unit ids.
    _prune_cypher, prune_params = calls[1]
    assert prune_params["keep"] == [str(_UNIT_ID)]

    # The facet links carry the inference payload and the bound jurisdiction.
    link_calls = [p for c, p in calls if "$confidence" in c]
    assert len(link_calls) == 2
    by_type = {p["facet_type"]: p for p in link_calls}
    assert by_type["task"]["status"] == "confirmed"
    assert by_type["task"]["basis"] == "anchor"
    assert by_type["meeting"]["confidence"] == 0.9
    assert all(p["jurisdiction"] == "eu-west" for p in link_calls)


def test_replace_units_empty_still_clears_the_tenant_subgraph() -> None:
    driver, session = _mock_driver()

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            await s.replace_units([])

    asyncio.run(run())
    calls = _all_calls(session)
    # Delete facets + prune (keep=[]) — no merges. Correlation that finds
    # nothing still tombstones the prior subgraph.
    assert len(calls) == 2
    assert calls[1][1]["keep"] == []


_OUTCOME_ID = UUID("00000000-0000-4000-8000-0000006700a1")


def test_replace_goal_edges_deletes_then_merges_with_bound_tenant() -> None:
    driver, session = _mock_driver()
    edge = GoalEdgeWrite(
        unit_id=_UNIT_ID,
        outcome_id=_OUTCOME_ID,
        confidence=0.9,
        status="confirmed",
        basis="commitment",
    )

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            await s.replace_goal_edges([edge])

    asyncio.run(run())
    calls = _all_calls(session)
    # delete SERVES, merge the one edge = 2 runs.
    assert len(calls) == 2
    for cypher, params in calls:
        assert params["tenant_id"] == _TENANT.tenant_id
        placeholders = set(re.findall(r"\$(\w+)", cypher))
        assert placeholders <= set(params), (cypher, placeholders - set(params))
    _merge_cypher, merge_params = calls[1]
    assert merge_params["unit_id"] == str(_UNIT_ID)
    assert merge_params["outcome_id"] == str(_OUTCOME_ID)
    assert merge_params["status"] == "confirmed"
    assert merge_params["basis"] == "commitment"
    # SERVES only — does not touch SAME_WORK or LEVER_FOR.
    assert "SAME_WORK" not in _merge_cypher and "LEVER_FOR" not in _merge_cypher


def test_replace_goal_edges_empty_still_clears() -> None:
    driver, session = _mock_driver()

    async def run() -> None:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            await s.replace_goal_edges([])

    asyncio.run(run())
    calls = _all_calls(session)
    assert len(calls) == 1  # delete only
    assert "SERVES" in calls[0][0]


def test_list_goal_edges_maps_rows() -> None:
    driver, session = _mock_driver()
    result = MagicMock()
    result.data = AsyncMock(
        return_value=[
            {
                "unit_id": str(_UNIT_ID),
                "outcome_id": str(_OUTCOME_ID),
                "confidence": 0.5,
                "status": "candidate",
                "basis": "goal-name",
            }
        ]
    )
    session.run = AsyncMock(return_value=result)

    async def run():
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            return list(await s.list_goal_edges())

    edges = asyncio.run(run())
    assert len(edges) == 1
    assert edges[0].unit_id == _UNIT_ID
    assert edges[0].outcome_id == _OUTCOME_ID
    assert edges[0].status == "candidate"
    assert edges[0].basis == "goal-name"


def _row(**overrides) -> dict:
    base = {
        "unit_id": str(_UNIT_ID),
        "facet_type": "task",
        "facet_id": str(_TASK_ID),
        "confidence": 1.0,
        "status": "confirmed",
        "basis": "anchor",
    }
    base.update(overrides)
    return base


def test_list_units_aggregates_facets_per_unit() -> None:
    driver, session = _mock_driver()
    result = MagicMock()
    result.data = AsyncMock(
        return_value=[
            _row(),
            _row(
                facet_type="meeting",
                facet_id=str(_MEETING_ID),
                confidence=0.9,
                status="confirmed",
                basis="title+time",
            ),
        ]
    )
    session.run = AsyncMock(return_value=result)

    async def run() -> list[UnitGraphRecord]:
        async with TenantScopedNeo4jSession(driver, _TENANT) as s:
            return list(await s.list_units())

    records = asyncio.run(run())
    assert len(records) == 1
    rec = records[0]
    assert rec.unit_id == _UNIT_ID
    assert len(rec.links) == 2
    kinds = {link.facet_type for link in rec.links}
    assert kinds == {"task", "meeting"}
    meeting_link = next(l for l in rec.links if l.facet_type == "meeting")
    assert meeting_link.confidence == 0.9
    assert meeting_link.basis == "title+time"
    assert meeting_link.facet_id == _MEETING_ID


# --- S103s hardening: the kind-vocabulary sync invariant (enforcement layer) ---
# The relink/unlink bug class this session chased one report at a time was always
# the same shape: a bindable kind added to one vocabulary but not swept into the
# adapter that resolves or normalises it. These three guards turn "every site was
# swept by hand" into "CI fails if a site is missed" — each would have caught a
# real S103k/S103s bug (D211's measurable_outcome) before it reached the browser.


def test_every_evidence_kind_resolves_to_a_cypher_endpoint():
    """Every kind a unit can bind to (EVIDENCE_KINDS — the router's relink/unlink
    whitelist) MUST resolve to a (label, id-property) Cypher endpoint. A kind in
    EVIDENCE_KINDS with no endpoint makes relink silently MATCH NOTHING — the
    "relink failed / no change" symptom. Adding a bindable kind without its
    endpoint fails here, not in the operator's browser."""
    from contexts.daily_driver.domain.cdd import EVIDENCE_KINDS
    from contexts.ingestion.adapters.outbound.neo4j.session import (
        _AUTHORED_ENDPOINT,
    )

    missing = EVIDENCE_KINDS - set(_AUTHORED_ENDPOINT)
    assert not missing, f"EVIDENCE_KINDS with no Cypher endpoint: {missing}"


def test_every_authored_element_kind_is_bindable():
    """Every authored ElementKind (lever/intermediary/external/measurable_outcome)
    MUST be in EVIDENCE_KINDS, or relink/unlink to it 422s at the router — the
    exact S103s bug where D211's measurable_outcome was authored but never added
    to the evidence whitelist."""
    from contexts.daily_driver.domain.cdd import EVIDENCE_KINDS, ElementKind

    missing = {k.value for k in ElementKind} - EVIDENCE_KINDS
    assert not missing, f"authored kinds that are not bindable: {missing}"


def test_every_evidence_kind_label_normalises_back_to_its_kind():
    """The read round-trip: bindings read a unit's endpoint kind from the node
    label (``labels(n)[0].lower()`` then ``_norm_edge_kind``). For every bindable
    kind that path MUST reproduce the kind string, or the read emits a kind the
    router rejects. :MeasurableOutcome lowercases to "measurableoutcome" and needs
    the alias (S103s) — a new underscore-bearing kind without its alias fails
    here rather than silently breaking relink."""
    from contexts.daily_driver.domain.cdd import EVIDENCE_KINDS
    from contexts.ingestion.adapters.outbound.neo4j.session import (
        _AUTHORED_ENDPOINT,
        _norm_edge_kind,
    )

    for kind in EVIDENCE_KINDS:
        label = _AUTHORED_ENDPOINT[kind][0]  # e.g. "MeasurableOutcome"
        assert _norm_edge_kind(label) == kind, (
            f"{label!r} normalises to {_norm_edge_kind(label)!r}, not {kind!r} — "
            "add its alias to _EDGE_KIND_ALIASES"
        )
