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
