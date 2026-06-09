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
        self, *, tenant_context, outcome_id, new_target_level
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
    # Inject today via the clock seam (S64/S75): the outcome resolves against
    # _NOW, not the real system date, so this is deterministic by construction
    # and cannot rot as real dates advance (the S74 wall-clock-by-luck flip).
    readings = asyncio.run(
        list_goals(
            goal_graph=graph,
            commitment_repository=repo,
            actor=_actor(),
            now=_NOW,
        )
    )
    assert len(readings) == 1
    assert readings[0].recommendation is RaiseOrHold.RAISE
    assert readings[0].next_target == "B2"


def test_list_goals_recommendation_depends_only_on_injected_now() -> None:
    """The RAISE/HOLD outcome is a function of the injected ``now`` alone, not
    the wall clock (S75). On-rhythm at _NOW → RAISE; far past the rhythm at a
    later injected date → HOLD. Pin both so neither can drift with real time."""
    graph = FakeGoalGraph(_goal())
    repo = FakeCommitmentRepo(_activity())  # last_completed_at = _NOW - 6h

    on_rhythm = asyncio.run(
        list_goals(
            goal_graph=graph, commitment_repository=repo, actor=_actor(), now=_NOW
        )
    )
    behind = asyncio.run(
        list_goals(
            goal_graph=graph,
            commitment_repository=repo,
            actor=_actor(),
            now=_NOW + timedelta(days=30),
        )
    )
    assert on_rhythm[0].recommendation is RaiseOrHold.RAISE
    assert behind[0].recommendation is RaiseOrHold.HOLD


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

    async def set_outcome_target(
        self, *, tenant_context, outcome_id, current_target_level
    ):
        self.set_to = current_target_level
        return current_target_level


def _progressive_record():
    from contexts.ingestion.ports.outcome_graph_port import (
        LeverEdgeRecord,
        OutcomeGraphRecord,
    )

    return OutcomeGraphRecord(
        outcome_id=_OUTCOME,
        name="German",
        control="self",
        subject="self",
        mode="progressive",
        ladder=_LADDER,
        current_target_level="B1",
        levers=(LeverEdgeRecord(commitment_id=_COMMITMENT),),
    )


def test_apps_bridge_maps_record_to_progressive_goal() -> None:
    from apps.api._daily_driver_wiring import GoalGraphAdapter

    adapter = GoalGraphAdapter(outcome_graph=FakeOutcomeGraph(_progressive_record()))
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
    assert g.steps == ()
    assert g.terminal is None


def test_apps_bridge_maps_record_to_homeostatic_goal_with_its_lever() -> None:
    # S69: a homeostatic goal carries a single lever; _to_goal must extract it
    # so the goal-facet confirmed tier (D169) can match the lever-commitment name.
    from apps.api._daily_driver_wiring import GoalGraphAdapter
    from contexts.ingestion.ports.outcome_graph_port import (
        LeverEdgeRecord,
        OutcomeGraphRecord,
    )

    record = OutcomeGraphRecord(
        outcome_id=_OUTCOME,
        name="Stretch and meditate",
        control="self",
        subject="self",
        mode="homeostatic",
        ladder=(),
        current_target_level=None,
        levers=(LeverEdgeRecord(commitment_id=_COMMITMENT),),
    )
    adapter = GoalGraphAdapter(outcome_graph=FakeOutcomeGraph(record))
    goals = asyncio.run(adapter.list_goals(tenant_context=_actor().tenant_context))
    g = goals[0]
    assert g.mode is GoalMode.HOMEOSTATIC
    assert g.lever_commitment_id == _COMMITMENT
    assert g.ladder is None
    assert g.terminal is None
    assert g.steps == ()


def test_apps_bridge_maps_record_to_sequence_goal() -> None:
    from apps.api._daily_driver_wiring import GoalGraphAdapter
    from contexts.daily_driver.domain.goal import StepState, TerminalState
    from contexts.ingestion.ports.outcome_graph_port import (
        LeverEdgeRecord,
        OutcomeGraphRecord,
    )

    seq = UUID("00000000-0000-4000-8000-0000006300a1")
    c1 = UUID("00000000-0000-4000-8000-0000006300c1")
    c2 = UUID("00000000-0000-4000-8000-0000006300c2")
    record = OutcomeGraphRecord(
        outcome_id=seq,
        name="Get a job",
        control="other",
        subject="self",
        mode="sequence",
        ladder=(),
        current_target_level=None,
        terminal_target="Offer accepted",
        terminal_state="pending",
        levers=(
            LeverEdgeRecord(commitment_id=c1, step_order=1, step_state="done"),
            LeverEdgeRecord(commitment_id=c2, step_order=2, step_state="blocked"),
        ),
    )
    adapter = GoalGraphAdapter(outcome_graph=FakeOutcomeGraph(record))
    goals = asyncio.run(
        adapter.list_goals(tenant_context=_actor().tenant_context)
    )
    assert len(goals) == 1
    g = goals[0]
    assert g.mode is GoalMode.SEQUENCE
    assert g.control is ControlAxis.OTHER  # the influence case
    assert g.subject is Subject.SELF
    assert g.terminal is not None
    assert g.terminal.target == "Offer accepted"
    assert g.terminal.state is TerminalState.PENDING
    assert len(g.steps) == 2
    assert g.ordered_steps[0].order == 1
    assert g.ordered_steps[0].state is StepState.DONE
    assert g.ordered_steps[1].state is StepState.BLOCKED
    assert g.ladder is None
    assert g.lever_commitment_id is None


def test_apps_bridge_raise_delegates_to_set_outcome_target() -> None:
    from apps.api._daily_driver_wiring import GoalGraphAdapter

    fake = FakeOutcomeGraph(_progressive_record())
    adapter = GoalGraphAdapter(outcome_graph=fake)
    result = asyncio.run(
        adapter.raise_target_level(
            tenant_context=_actor().tenant_context,
            outcome_id=_OUTCOME,
            new_target_level="B2",
        )
    )
    assert result == "B2"
    assert fake.set_to == "B2"
