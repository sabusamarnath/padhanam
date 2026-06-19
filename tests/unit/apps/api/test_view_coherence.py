"""View coherence: List/Map and CDD derive from one element-evidence source (S103c-fix-2).

The consistency guard: the goal-level edges List and Map read
(``UnitGraphAdapter.list_goal_edges``) are exactly ``derive_goal_edges`` of the
same element evidence the CDD view reads (``list_element_evidence``). If anyone
ever re-points one view at a diverging source, this fails. Synthetic — no PII.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from apps.api._daily_driver_wiring import UnitGraphAdapter
from contexts.daily_driver.domain.goal_assessment import derive_goal_edges
from contexts.ingestion.ports.unit_graph_port import ElementEvidenceRecord


class _FakeIngestionUnitGraph:
    """The ingestion-side graph the bridge wraps — returns element evidence."""

    def __init__(self, records):
        self._records = records

    async def list_element_evidence(self, *, tenant_context):
        return self._records


def _rec(unit, element_id, outcome, kind="lever", tier="lexical_exact",
         status="confirmed", basis="element-exact"):
    return ElementEvidenceRecord(
        unit_id=unit, element_kind=kind, element_id=element_id,
        outcome_id=outcome, tier=tier, status=status, basis=basis,
    )


def test_list_map_goal_edges_are_derived_from_the_cdd_element_evidence():
    # One unit multi-attached to two elements in one goal + one in another.
    u = uuid4(); g1 = uuid4(); g2 = uuid4()
    records = (
        _rec(u, uuid4(), g1, tier="lexical_keyword", status="candidate", basis="element-keyword"),
        _rec(u, uuid4(), g1, tier="lexical_exact", status="confirmed", basis="element-exact"),
        _rec(u, uuid4(), g2, tier="lexical_exact", status="confirmed", basis="element-exact"),
    )
    bridge = UnitGraphAdapter(unit_graph=_FakeIngestionUnitGraph(records))

    # The CDD source (element evidence) and the List/Map source (goal edges) must
    # be the one truth: list_goal_edges == derive_goal_edges(list_element_evidence).
    evidence = asyncio.run(bridge.list_element_evidence(tenant_context=None))
    goal_edges = asyncio.run(bridge.list_goal_edges(tenant_context=None))
    assert goal_edges == derive_goal_edges(evidence)
    # And the rollup is coherent: one goal edge per (unit, goal), strongest wins.
    by_goal = {(e.unit_id, e.outcome_id): e for e in goal_edges}
    assert len(by_goal) == 2  # g1 (multi-attach collapsed) + g2
    assert by_goal[(u, g1)].status.value == "confirmed"  # exact beat keyword
