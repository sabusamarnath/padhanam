"""Application + bridge tests for the goal layer (S62, D163).

In-memory fakes exercise list_goals (graph + lever-activity join), the
authorisation boundary, raise_goal_target (explicit, never auto), and the apps
GoalGraphAdapter's record->Goal mapping — without a database or Neo4j.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from contexts.daily_driver.application import list_goals, raise_goal_target
from contexts.daily_driver.domain.commitment import (
    Commitment,
    CommitmentActivity,
    OutcomeStatus,
)
from contexts.daily_driver.domain.goal import (
    ControlAxis,
    Goal,
    GoalMode,
    LevelLadder,
    Subject,
)
from contexts.daily_driver.domain.goal_view import RaiseOrHold
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import (
    AuthorisationDenied,
    ROLE_OPERATOR,
    authorisations_for_roles,
)

_TENANT = "00000000-0000-4000-8000-00000000d001"
_OUTCOME = UUID("00000000-0000-4000-8000-0000006200a1")
_COMMITMENT = UUID("00000000-0000-4000-8000-000000620c01")
_NOW = datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc)
_LADDER = ("A1", "A2", "B1", "B2", "C1", "C2")


def _actor(*, authorised: bool = True) -> ActorContext:
    roles = frozenset({ROLE_OPERATOR}) if authorised else frozenset({"viewer"})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _goal(target: str = "B1") -> Goal:
    return Goal(
        id=_OUTCOME,
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        name="German",
        mode=GoalMode.PROGRESSIVE,
        control=ControlAxis.SELF,
        subject=Subject.SELF,
        lever_commitment_id=_COMMITMENT,
        ladder=LevelLadder(levels=_LADDER, current_target_level=target),
    )


class FakeGoalGraph:
    def __init__(self, goal: Goal) -> None:
        self._goal = goal
        self.raised_to: str | None = None

    async def list_goals(self, *, tenant_context):
        return (self._goal,)

    async def raise_target_level(
        self, *, tenant_context, outcome_id, commitment_id, new_target_level
    ):
        self.raised_to = new_target_level
        return new_target_level


class FakeCommitmentRepo:
    def __init__(self, activity: CommitmentActivity) -> None:
        self._activity = activity

    async def list_with_activity(self, *, tenant_context):
        return (self._activity,)


def _activity() -> CommitmentActivity:
    commitment = Commitment(
        id=_COMMITMENT,
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        name="German practice",
        expected_interval_days=1,
        authored_by_user_id="operator-001",
        created_at=_NOW - timedelta(days=30),
        expected_outcome="toward fluency",
        observed_outcome="solid week",
        outcome_status=OutcomeStatus.MET,
        observed_at=_NOW - timedelta(hours=2),
    )
    return CommitmentActivity(
        commitment=commitment, last_completed_at=_NOW - timedelta(hours=6)
    )


def test_list_goals_joins_lever_and_recommends_raise() -> None:
    graph = FakeGoalGraph(_goal())
    repo = FakeCommitmentRepo(_activity())
    readings = asyncio.run(
        list_goals(goal_graph=graph, commitment_repository=repo, actor=_actor())
    )
    assert len(readings) == 1
    assert readings[0].recommendation is RaiseOrHold.RAISE
    assert readings[0].next_target == "B2"


def test_list_goals_unauthorised_denied() -> None:
    graph = FakeGoalGraph(_goal())
    repo = FakeCommitmentRepo(_activity())
    with pytest.raises(AuthorisationDenied):
        asyncio.run(
            list_goals(
                goal_graph=graph,
                commitment_repository=repo,
                actor=_actor(authorised=False),
            )
        )


def test_raise_goal_target_moves_one_level_up() -> None:
    graph = FakeGoalGraph(_goal(target="B1"))
    new = asyncio.run(
        raise_goal_target(goal_graph=graph, actor=_actor(), outcome_id=_OUTCOME)
    )
    assert new == "B2"
    assert graph.raised_to == "B2"


def test_raise_goal_target_at_top_is_noop() -> None:
    graph = FakeGoalGraph(_goal(target="C2"))
    new = asyncio.run(
        raise_goal_target(goal_graph=graph, actor=_actor(), outcome_id=_OUTCOME)
    )
    assert new is None
    assert graph.raised_to is None


def test_raise_goal_target_unknown_outcome_is_noop() -> None:
    graph = FakeGoalGraph(_goal())
    new = asyncio.run(
        raise_goal_target(
            goal_graph=graph,
            actor=_actor(),
            outcome_id=UUID("00000000-0000-4000-8000-0000000000ff"),
        )
    )
    assert new is None


def test_raise_goal_target_unauthorised_denied() -> None:
    graph = FakeGoalGraph(_goal())
    with pytest.raises(AuthorisationDenied):
        asyncio.run(
            raise_goal_target(
                goal_graph=graph,
                actor=_actor(authorised=False),
                outcome_id=_OUTCOME,
            )
        )


# --- apps bridge: GoalGraphAdapter record -> Goal mapping ------------------


class FakeOutcomeGraph:
    def __init__(self, record) -> None:
        self._record = record
        self.set_to: str | None = None

    async def list_outcomes(self, *, tenant_context):
        return (self._record,)

    async def set_lever_target(
        self, *, tenant_context, outcome_id, commitment_id, current_target_level
    ):
        self.set_to = current_target_level
        return current_target_level


def test_apps_bridge_maps_record_to_progressive_goal() -> None:
    from apps.api._daily_driver_wiring import GoalGraphAdapter
    from contexts.ingestion.ports.outcome_graph_port import OutcomeGraphRecord

    record = OutcomeGraphRecord(
        outcome_id=_OUTCOME,
        name="German",
        control="self",
        subject="self",
        commitment_id=_COMMITMENT,
        mode="progressive",
        ladder=_LADDER,
        current_target_level="B1",
    )
    adapter = GoalGraphAdapter(outcome_graph=FakeOutcomeGraph(record))
    goals = asyncio.run(
        adapter.list_goals(tenant_context=_actor().tenant_context)
    )
    assert len(goals) == 1
    g = goals[0]
    assert g.mode is GoalMode.PROGRESSIVE
    assert g.control is ControlAxis.SELF
    assert g.subject is Subject.SELF
    assert g.ladder is not None
    assert g.ladder.current_target_level == "B1"
    assert g.lever_commitment_id == _COMMITMENT


def test_apps_bridge_raise_delegates_to_set_lever_target() -> None:
    from apps.api._daily_driver_wiring import GoalGraphAdapter
    from contexts.ingestion.ports.outcome_graph_port import OutcomeGraphRecord

    record = OutcomeGraphRecord(
        outcome_id=_OUTCOME,
        name="German",
        control="self",
        subject="self",
        commitment_id=_COMMITMENT,
        mode="progressive",
        ladder=_LADDER,
        current_target_level="B1",
    )
    fake = FakeOutcomeGraph(record)
    adapter = GoalGraphAdapter(outcome_graph=fake)
    result = asyncio.run(
        adapter.raise_target_level(
            tenant_context=_actor().tenant_context,
            outcome_id=_OUTCOME,
            commitment_id=_COMMITMENT,
            new_target_level="B2",
        )
    )
    assert result == "B2"
    assert fake.set_to == "B2"
