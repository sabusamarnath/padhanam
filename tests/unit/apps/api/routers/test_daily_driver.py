"""Route tests for the daily-driver HTTP surface (D157, S58).

A bare FastAPI app carries the daily-driver router and fakes on
app.state; ``get_actor_context`` is dependency-overridden to a fully
authorised ActorContext. Exercises the read aggregation, commitment
creation, the completion loop, ordering, and the done overlay through
HTTP — no auth middleware (the authentication path is tested elsewhere).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.middleware import get_actor_context
from apps.api.routers import daily_driver as daily_driver_router
from contexts.daily_driver.domain.commitment import (
    Commitment,
    CommitmentActivity,
    CommitmentCompletion,
)
from contexts.daily_driver.domain.day import DayItemState, item_key
from contexts.daily_driver.domain.today_item import ItemKind, OpenCase
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000a001"


def _actor_context() -> ActorContext:
    roles = frozenset({"operator"})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


class _FakeCommitmentRepo:
    def __init__(self) -> None:
        self.commitments: dict[UUID, Commitment] = {}
        self.completions: list[CommitmentCompletion] = []

    async def add_commitment(self, *, tenant_context, commitment) -> None:
        self.commitments[commitment.id] = commitment

    async def add_completion(self, *, tenant_context, completion) -> None:
        self.completions.append(completion)

    async def get_commitment(self, *, tenant_context, commitment_id):
        return self.commitments.get(commitment_id)

    async def record_observed_outcome(
        self,
        *,
        tenant_context,
        commitment_id,
        observed_outcome,
        outcome_status,
        observed_at,
    ):
        from dataclasses import replace

        existing = self.commitments.get(commitment_id)
        if existing is None:
            return None
        updated = replace(
            existing,
            observed_outcome=observed_outcome,
            outcome_status=outcome_status,
            observed_at=observed_at,
        )
        self.commitments[commitment_id] = updated
        return updated

    async def list_with_activity(self, *, tenant_context):
        out = []
        for c in self.commitments.values():
            times = [x.completed_at for x in self.completions if x.commitment_id == c.id]
            out.append(CommitmentActivity(c, max(times) if times else None))
        return tuple(out)


class _FakeDayRepo:
    def __init__(self) -> None:
        self.states: dict[str, DayItemState] = {}

    async def get_states(self, *, tenant_context, user_id, day_date):
        return tuple(self.states.values())

    async def set_positions(self, *, tenant_context, user_id, day_date, ordered_keys):
        for pos, (kind, item_id) in enumerate(ordered_keys):
            self.states[item_key(kind, item_id)] = DayItemState(
                kind=kind, item_id=item_id, position=pos, done=False
            )

    async def set_done(self, *, tenant_context, user_id, day_date, kind, item_id, done):
        self.states[item_key(kind, item_id)] = DayItemState(
            kind=kind, item_id=item_id, position=None, done=done
        )


class _FakeOpenCases:
    def __init__(self, cases) -> None:
        self._cases = cases

    async def list_open_cases(self, *, actor):
        return self._cases


def _client(
    commit_repo, day_repo, open_cases, *, quiet_days=None, goal_graph=None
) -> TestClient:
    app = FastAPI()
    app.include_router(daily_driver_router.router)
    app.state.daily_driver_commitment_repository = commit_repo
    app.state.daily_driver_day_repository = day_repo
    app.state.daily_driver_open_cases_reader = open_cases
    app.state.daily_driver_drop_candidate_quiet_days = quiet_days
    app.state.daily_driver_goal_graph = goal_graph
    app.dependency_overrides[get_actor_context] = _actor_context
    return TestClient(app)


def test_today_lists_open_case_and_overdue_commitment_first() -> None:
    repo = _FakeCommitmentRepo()
    overdue = Commitment(
        id=uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        name="Weekly review",
        expected_interval_days=7,
        authored_by_user_id="operator-001",
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    repo.commitments[overdue.id] = overdue
    case = OpenCase(case_id=uuid4(), title="Launch plan", created_at=datetime.now(timezone.utc))
    client = _client(repo, _FakeDayRepo(), _FakeOpenCases((case,)))

    res = client.get("/api/v1/daily-driver/today")
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert items[0]["status"] == "BEHIND"
    assert items[0]["title"] == "Weekly review"
    assert items[0]["overdue_by_days"] is not None
    assert any(i["status"] == "NEEDS_YOU" for i in items)


def test_create_commitment_then_complete_clears_overdue() -> None:
    repo = _FakeCommitmentRepo()
    client = _client(repo, _FakeDayRepo(), _FakeOpenCases(()))

    created = client.post(
        "/api/v1/daily-driver/commitments",
        json={"name": "Daily standup", "expected_interval_days": 1},
    )
    assert created.status_code == 201, created.text
    commitment_id = created.json()["id"]

    completion = client.post(
        f"/api/v1/daily-driver/commitments/{commitment_id}/completions"
    )
    assert completion.status_code == 201, completion.text
    assert completion.json()["commitment_id"] == commitment_id


def test_complete_unknown_commitment_404() -> None:
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()))
    res = client.post(f"/api/v1/daily-driver/commitments/{uuid4()}/completions")
    assert res.status_code == 404


# --- S61 (D162): the expected-versus-observed loop over HTTP --------


def test_create_with_expected_outcome_round_trips() -> None:
    repo = _FakeCommitmentRepo()
    client = _client(repo, _FakeDayRepo(), _FakeOpenCases(()))
    res = client.post(
        "/api/v1/daily-driver/commitments",
        json={
            "name": "Mentor Priya",
            "expected_interval_days": 7,
            "expected_outcome": "she leads the migration",
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["expected_outcome"] == "she leads the migration"


def test_record_observed_outcome_route() -> None:
    repo = _FakeCommitmentRepo()
    client = _client(repo, _FakeDayRepo(), _FakeOpenCases(()))
    created = client.post(
        "/api/v1/daily-driver/commitments",
        json={"name": "Mentor Priya", "expected_interval_days": 7},
    )
    cid = created.json()["id"]
    res = client.post(
        f"/api/v1/daily-driver/commitments/{cid}/observed-outcome",
        json={"observed_outcome": "she led it", "outcome_status": "met"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["observed_outcome"] == "she led it"
    assert body["outcome_status"] == "met"
    assert body["observed_at"] is not None


def test_record_observed_outcome_unknown_404() -> None:
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()))
    res = client.post(
        f"/api/v1/daily-driver/commitments/{uuid4()}/observed-outcome",
        json={"outcome_status": "dropped"},
    )
    assert res.status_code == 404


def test_record_observed_outcome_rejects_unknown_status() -> None:
    repo = _FakeCommitmentRepo()
    client = _client(repo, _FakeDayRepo(), _FakeOpenCases(()))
    created = client.post(
        "/api/v1/daily-driver/commitments",
        json={"name": "X", "expected_interval_days": 7},
    )
    cid = created.json()["id"]
    res = client.post(
        f"/api/v1/daily-driver/commitments/{cid}/observed-outcome",
        json={"outcome_status": "abandoned"},
    )
    assert res.status_code == 422


def test_today_flags_drop_candidate_when_configured() -> None:
    repo = _FakeCommitmentRepo()
    quiet = Commitment(
        id=uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        name="Old habit",
        expected_interval_days=7,
        authored_by_user_id="operator-001",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    repo.commitments[quiet.id] = quiet
    client = _client(repo, _FakeDayRepo(), _FakeOpenCases(()), quiet_days=21)
    items = client.get("/api/v1/daily-driver/today").json()["items"]
    assert items[0]["drop_candidate"] is True


def test_today_no_drop_candidate_when_threshold_unset() -> None:
    repo = _FakeCommitmentRepo()
    quiet = Commitment(
        id=uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        name="Old habit",
        expected_interval_days=7,
        authored_by_user_id="operator-001",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    repo.commitments[quiet.id] = quiet
    client = _client(repo, _FakeDayRepo(), _FakeOpenCases(()))
    items = client.get("/api/v1/daily-driver/today").json()["items"]
    assert items[0]["drop_candidate"] is False


def test_mark_done_and_reorder_persist() -> None:
    repo = _FakeCommitmentRepo()
    day = _FakeDayRepo()
    case = OpenCase(case_id=uuid4(), title="Launch plan", created_at=datetime.now(timezone.utc))
    client = _client(repo, day, _FakeOpenCases((case,)))

    done = client.post(
        "/api/v1/daily-driver/today/done",
        json={"kind": "CASE", "item_id": str(case.case_id), "done": True},
    )
    assert done.status_code == 204
    assert day.states[item_key(ItemKind.CASE, case.case_id)].done is True

    order = client.put(
        "/api/v1/daily-driver/today/order",
        json={"ordered": [{"kind": "CASE", "item_id": str(case.case_id)}]},
    )
    assert order.status_code == 204
    assert day.states[item_key(ItemKind.CASE, case.case_id)].position == 0


# --- Goal layer routes (S62, D163) ---------------------------------------

_OUTCOME = UUID("00000000-0000-4000-8000-0000006200a1")
_GERMAN_COMMITMENT = UUID("00000000-0000-4000-8000-000000620c01")


def _german_goal(target="B1"):
    from contexts.daily_driver.domain.goal import (
        ControlAxis,
        Goal,
        GoalMode,
        LevelLadder,
        Subject,
    )

    return Goal(
        id=_OUTCOME,
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        name="German",
        mode=GoalMode.PROGRESSIVE,
        control=ControlAxis.SELF,
        subject=Subject.SELF,
        lever_commitment_id=_GERMAN_COMMITMENT,
        ladder=LevelLadder(
            levels=("A1", "A2", "B1", "B2", "C1", "C2"), current_target_level=target
        ),
    )


class _FakeGoalGraph:
    def __init__(self, goal) -> None:
        self._goal = goal
        self.raised_to = None

    async def list_goals(self, *, tenant_context):
        return (self._goal,)

    async def raise_target_level(
        self, *, tenant_context, outcome_id, new_target_level
    ):
        self.raised_to = new_target_level
        from dataclasses import replace

        self._goal = replace(
            self._goal,
            ladder=replace(self._goal.ladder, current_target_level=new_target_level),
        )
        return new_target_level


def _german_commitment_repo():
    from contexts.daily_driver.domain.commitment import OutcomeStatus

    repo = _FakeCommitmentRepo()
    commitment = Commitment(
        id=_GERMAN_COMMITMENT,
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        name="German practice",
        expected_interval_days=1,
        authored_by_user_id="operator-001",
        created_at=datetime.now(timezone.utc),
        expected_outcome="toward fluency",
        observed_outcome="solid week",
        outcome_status=OutcomeStatus.MET,
        observed_at=datetime.now(timezone.utc),
    )
    repo.commitments[commitment.id] = commitment
    # A recent completion keeps the daily cadence on track.
    repo.completions.append(
        CommitmentCompletion(
            id=uuid4(),
            commitment_id=commitment.id,
            tenant_id=UUID(_TENANT),
            jurisdiction="eu-west",
            completed_at=datetime.now(timezone.utc),
        )
    )
    return repo


def test_goals_route_returns_german_reading() -> None:
    graph = _FakeGoalGraph(_german_goal())
    client = _client(
        _german_commitment_repo(), _FakeDayRepo(), _FakeOpenCases(()), goal_graph=graph
    )
    res = client.get("/api/v1/daily-driver/goals")
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body) == 1
    g = body[0]
    assert g["name"] == "German"
    assert g["current_target"] == "B1"
    assert g["recommendation"] == "raise"
    assert g["next_target"] == "B2"


def test_raise_target_route_raises_one_level() -> None:
    graph = _FakeGoalGraph(_german_goal())
    client = _client(
        _german_commitment_repo(), _FakeDayRepo(), _FakeOpenCases(()), goal_graph=graph
    )
    res = client.post(f"/api/v1/daily-driver/goals/{_OUTCOME}/raise-target")
    assert res.status_code == 200, res.text
    assert graph.raised_to == "B2"
    assert res.json()["current_target"] == "B2"


def test_raise_target_at_top_409() -> None:
    graph = _FakeGoalGraph(_german_goal(target="C2"))
    client = _client(
        _german_commitment_repo(), _FakeDayRepo(), _FakeOpenCases(()), goal_graph=graph
    )
    res = client.post(f"/api/v1/daily-driver/goals/{_OUTCOME}/raise-target")
    assert res.status_code == 409
    assert graph.raised_to is None


_SEQ_OUTCOME = UUID("00000000-0000-4000-8000-0000006300a1")


def _get_a_job_goal():
    from contexts.daily_driver.domain.goal import (
        ControlAxis,
        Goal,
        GoalMode,
        LeverStep,
        StepState,
        Subject,
        Terminal,
        TerminalState,
    )

    return Goal(
        id=_SEQ_OUTCOME,
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        name="Get a job",
        mode=GoalMode.SEQUENCE,
        control=ControlAxis.OTHER,
        subject=Subject.SELF,
        terminal=Terminal(target="Offer accepted", state=TerminalState.PENDING),
        steps=(
            LeverStep(
                commitment_id=UUID("00000000-0000-4000-8000-0000006300c1"),
                order=1,
                state=StepState.DONE,
            ),
            LeverStep(
                commitment_id=UUID("00000000-0000-4000-8000-0000006300c2"),
                order=2,
                state=StepState.BLOCKED,
            ),
        ),
    )


def test_goals_route_returns_unblock_or_drop_for_sequence() -> None:
    # AC5/AC6: a sequence goal surfaces its chain + unblock-or-drop, and never
    # raise-or-hold.
    graph = _FakeGoalGraph(_get_a_job_goal())
    client = _client(
        _FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()), goal_graph=graph
    )
    res = client.get("/api/v1/daily-driver/goals")
    assert res.status_code == 200, res.text
    g = res.json()[0]
    assert g["name"] == "Get a job"
    assert g["mode"] == "sequence"
    assert g["control"] == "other"  # the influence case
    assert g["remedy_kind"] == "unblock_or_drop"
    assert g["recommendation"] == "unblock"
    assert g["recommendation"] not in ("raise", "hold")
    assert g["terminal_target"] == "Offer accepted"
    assert g["terminal_state"] == "pending"
    assert len(g["steps"]) == 2
    assert g["current_target"] is None  # no ladder on a sequence goal
