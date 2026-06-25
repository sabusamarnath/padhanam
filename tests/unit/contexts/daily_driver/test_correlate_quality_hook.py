"""The matcher-quality hook is observe-only (D185, S90).

``correlate_goal_facets`` gains an optional recorder; wiring it must not change
the edges the matcher writes. The recorder must receive exactly the edge set that
is replaced, plus the units. Synthetic fixtures — no PII.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from contexts.daily_driver.application import correlate_goal_facets
from contexts.daily_driver.domain.cdd import GoalCddView
from contexts.daily_driver.domain.goal_assessment import derive_goal_edges
from contexts.daily_driver.domain.goal import (
    ControlAxis,
    Goal,
    GoalMode,
    LevelLadder,
    Subject,
)
from contexts.daily_driver.domain.work_unit import (
    FacetType,
    LinkStatus,
    UnitFacetRef,
    UnitRecord,
    WorkFacet,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000d001"


def _actor() -> ActorContext:
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _goal(name: str) -> Goal:
    from uuid import UUID

    return Goal(
        id=uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        name=name,
        mode=GoalMode.PROGRESSIVE,
        control=ControlAxis.SELF,
        subject=Subject.SELF,
        lever_commitment_id=uuid4(),
        ladder=LevelLadder(levels=("A1", "A2", "B1"), current_target_level="A2"),
    )


class _FakeUnitGraph:
    def __init__(self, records):
        self._records = records
        self.replaced = None

    async def list_units(self, *, tenant_context):
        return self._records

    async def list_user_owned_unit_ids(self, *, tenant_context):
        return set()

    async def list_clustered_unit_ids(self, *, tenant_context):
        return set()


    async def replace_element_evidence(self, *, tenant_context, evidence):
        self.replaced = tuple(evidence)


class _FakeFacetSource:
    def __init__(self, facets):
        self._facets = facets

    async def list_facets(self, *, actor):
        return self._facets


class _FakeGoalGraph:
    """Goals with empty CDDs (S103b): a unit keyword-matching the goal name binds
    to the goal's outcome element at the alias tier, so an edge still forms."""

    def __init__(self, goals):
        self._goals = goals

    async def list_goals(self, *, tenant_context):
        return self._goals

    async def read_goal_cdd(self, *, tenant_context, outcome_id):
        return GoalCddView(
            outcome_id=outcome_id, expected_outcome="", elements=(), edges=()
        )


class _FakeCommitmentRepo:
    async def list_with_activity(self, *, tenant_context):
        return ()


class _RecordingRecorder:
    def __init__(self):
        self.edges = None
        self.units = None
        self.calls = 0

    async def record(self, *, actor, edges, units):
        self.calls += 1
        self.edges = edges
        self.units = units


def _fixture():
    f1 = uuid4()
    records = (
        UnitRecord(
            unit_id=uuid4(),
            facets=(
                UnitFacetRef(
                    facet_type=FacetType.TASK,
                    facet_id=f1,
                    confidence=1.0,
                    status=LinkStatus.CONFIRMED,
                    basis="anchor",
                ),
            ),
        ),
    )
    facets = (
        WorkFacet(
            facet_type=FacetType.TASK,
            facet_id=f1,
            title="Marathon training plan",
            occurred_at=None,
        ),
    )
    goals = (_goal("Marathon"),)  # keyword 'marathon' -> a goal-name candidate edge
    return records, facets, goals


def _run(fixture, *, recorder=None):
    records, facets, goals = fixture
    ug = _FakeUnitGraph(records)
    n = asyncio.run(
        correlate_goal_facets(
            unit_graph=ug,
            facet_source=_FakeFacetSource(facets),
            goal_graph=_FakeGoalGraph(goals),
            commitment_repository=_FakeCommitmentRepo(),
            matcher_quality_recorder=recorder,
            actor=_actor(),
        )
    )
    return n, ug


def test_recorder_does_not_change_the_replaced_edges() -> None:
    fixture = _fixture()  # one fixture, both runs — same ids, so edges compare
    n_without, ug_without = _run(fixture)
    rec = _RecordingRecorder()
    n_with, ug_with = _run(fixture, recorder=rec)
    # the matcher's output is identical whether or not the recorder is wired
    assert n_without == n_with
    assert ug_without.replaced == ug_with.replaced
    # a real edge formed (so the test is not vacuously true)
    assert n_with >= 1


def test_recorder_receives_exactly_the_replaced_edges_and_units() -> None:
    rec = _RecordingRecorder()
    _, ug = _run(_fixture(), recorder=rec)
    assert rec.calls == 1
    # The producer is goal-shaped: the recorder measures the goal-level rollup
    # derived from exactly the element evidence that was written (D202, S103b).
    assert rec.edges == derive_goal_edges(ug.replaced)
    assert rec.units is not None and len(rec.units) == 1
