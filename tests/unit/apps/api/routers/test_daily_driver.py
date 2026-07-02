"""Route tests for the daily-driver HTTP surface (D157, S58).

A bare FastAPI app carries the daily-driver router and fakes on
app.state; ``get_actor_context`` is dependency-overridden to a fully
authorised ActorContext. Exercises the read aggregation, commitment
creation, the completion loop, ordering, and the done overlay through
HTTP — no auth middleware (the authentication path is tested elsewhere).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    commit_repo,
    day_repo,
    open_cases,
    *,
    quiet_days=None,
    goal_graph=None,
    tasks_reader=None,
    unit_graph=None,
    facet_source=None,
) -> TestClient:
    app = FastAPI()
    app.include_router(daily_driver_router.router)
    app.state.daily_driver_commitment_repository = commit_repo
    app.state.daily_driver_day_repository = day_repo
    app.state.daily_driver_open_cases_reader = open_cases
    app.state.daily_driver_drop_candidate_quiet_days = quiet_days
    app.state.daily_driver_goal_graph = goal_graph
    app.state.daily_driver_tasks_reader = tasks_reader
    app.state.daily_driver_unit_graph = unit_graph
    app.state.daily_driver_facet_source = facet_source
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


def test_act_worklist_unions_commitments_and_cases_tagged_and_sorted() -> None:
    # The pipeline seams are absent (unit_graph/facet_source None) so the model
    # sources degrade; the act read still unions commitments + cases (D232).
    repo = _FakeCommitmentRepo()
    overdue = Commitment(
        id=uuid4(), tenant_id=UUID(_TENANT), jurisdiction="eu-west",
        name="Weekly review", expected_interval_days=7,
        authored_by_user_id="operator-001",
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    repo.commitments[overdue.id] = overdue
    case = OpenCase(case_id=uuid4(), title="Launch plan", created_at=datetime.now(timezone.utc))
    client = _client(repo, _FakeDayRepo(), _FakeOpenCases((case,)))

    res = client.get("/api/v1/daily-driver/act")
    assert res.status_code == 200, res.text
    body = res.json()
    sources = {i["source"] for i in body["items"]}
    assert sources == {"commitment", "case"}
    # most overdue first: the long-overdue commitment precedes the due-today case.
    assert body["items"][0]["source"] == "commitment"
    assert body["items"][0]["due_in_days"] < 0
    assert body["items"][0]["horizon"] == "overdue"
    case_item = next(i for i in body["items"] if i["source"] == "case")
    assert case_item["due_in_days"] == 0 and case_item["is_opportunity"] is False
    assert case_item["ref"]["kind"] == "CASE"


def test_act_worklist_week_horizon_excludes_day_eight() -> None:
    repo = _FakeCommitmentRepo()
    # created 22 days ago on a 30-day cadence → due in 8 days: NOT in the week cut.
    far = Commitment(
        id=uuid4(), tenant_id=UUID(_TENANT), jurisdiction="eu-west",
        name="Monthly report", expected_interval_days=30,
        authored_by_user_id="operator-001",
        created_at=datetime.now(timezone.utc) - timedelta(days=22),
    )
    repo.commitments[far.id] = far
    client = _client(repo, _FakeDayRepo(), _FakeOpenCases(()))
    item = client.get("/api/v1/daily-driver/act").json()["items"][0]
    assert item["due_in_days"] == 8
    assert item["horizon"] == "later"  # beyond the seven-day week


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


class _FakeTasksReader:
    def __init__(self, tasks) -> None:
        self._tasks = tasks

    async def list_tasks(self, *, actor, include_completed=True):
        return tuple(self._tasks)


def _task(gid="t1", *, status="needsAction", title="Apply to roles"):
    from contexts.tasks.domain.task import Task, TaskStatus

    return Task(
        id=uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        google_task_id=gid,
        tasklist_id="L1",
        tasklist_title="My Tasks",
        status=TaskStatus(status),
        title=title,
        notes="shortlist five",
        due_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
        completed_at=None,
        parent=None,
        position=None,
        source_updated_at=None,
        content_hash="h",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_tasks_route_returns_ingested_tasks() -> None:
    client = _client(
        _FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()),
        tasks_reader=_FakeTasksReader([_task("t1"), _task("t2", title="Refresh CV")]),
    )
    res = client.get("/api/v1/daily-driver/tasks")
    assert res.status_code == 200, res.text
    body = res.json()
    assert [t["google_task_id"] for t in body] == ["t1", "t2"]
    assert body[0]["title"] == "Apply to roles"
    assert body[0]["tasklist_title"] == "My Tasks"
    assert body[0]["status"] == "needsAction"


def test_tasks_route_empty_when_reader_unwired() -> None:
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()))
    res = client.get("/api/v1/daily-driver/tasks")
    assert res.status_code == 200
    assert res.json() == []


class _FakeUnitGraph:
    """In-memory UnitGraphPort returning pre-set thin UnitRecords + goal edges."""

    def __init__(self, records, goal_edges=()) -> None:
        self._records = records
        self._goal_edges = goal_edges

    async def list_units(self, *, tenant_context):
        return tuple(self._records)

    async def list_goal_edges(self, *, tenant_context):
        return tuple(self._goal_edges)


class _FakeFacetSource:
    def __init__(self, facets) -> None:
        self._facets = facets

    async def list_facets(self, *, actor):
        return tuple(self._facets)


def test_units_route_returns_correlated_unit_with_grouped_facets() -> None:
    from contexts.daily_driver.domain.work_unit import (
        FacetType,
        LinkStatus,
        WorkFacet,
    )
    from contexts.daily_driver.ports.unit_graph import UnitFacetRef, UnitRecord

    task_id = uuid4()
    meeting_id = uuid4()
    unit_id = uuid4()
    record = UnitRecord(
        unit_id=unit_id,
        facets=(
            UnitFacetRef(
                facet_type=FacetType.TASK, facet_id=task_id,
                confidence=1.0, status=LinkStatus.CONFIRMED, basis="anchor",
            ),
            UnitFacetRef(
                facet_type=FacetType.MEETING, facet_id=meeting_id,
                confidence=0.9, status=LinkStatus.CONFIRMED, basis="title+time",
            ),
        ),
    )
    facets = [
        WorkFacet(FacetType.TASK, task_id, "Ship Q3 report", None),
        WorkFacet(FacetType.MEETING, meeting_id, "Ship Q3 report", None),
    ]
    client = _client(
        _FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()),
        unit_graph=_FakeUnitGraph([record]),
        facet_source=_FakeFacetSource(facets),
    )
    res = client.get("/api/v1/daily-driver/units")
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body) == 1
    unit = body[0]
    assert unit["is_correlated"] is True
    assert unit["title"] == "Ship Q3 report"
    assert {f["facet_type"] for f in unit["facets"]} == {"task", "meeting"}
    assert all(f["present"] for f in unit["facets"])


def test_units_route_empty_when_seams_unwired() -> None:
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()))
    res = client.get("/api/v1/daily-driver/units")
    assert res.status_code == 200
    assert res.json() == []


class _FakeGoalGraphForAssessment:
    def __init__(self, goals) -> None:
        self._goals = goals

    async def list_goals(self, *, tenant_context):
        return tuple(self._goals)


def test_assessment_route_returns_coverage_uncovered_and_orphan() -> None:
    from contexts.daily_driver.domain.goal import (
        ControlAxis, Goal, GoalMode, LevelLadder, Subject,
    )
    from contexts.daily_driver.domain.goal_assessment import GoalEdge
    from contexts.daily_driver.domain.work_unit import (
        FacetType, LinkStatus, WorkFacet,
    )
    from contexts.daily_driver.ports.unit_graph import UnitFacetRef, UnitRecord

    served_unit, orphan_unit = uuid4(), uuid4()
    task_a, task_b = uuid4(), uuid4()
    served_goal_id, neglected_goal_id = uuid4(), uuid4()
    cid = uuid4()
    records = [
        UnitRecord(served_unit, (UnitFacetRef(
            FacetType.TASK, task_a, 1.0, LinkStatus.CONFIRMED, "anchor"),)),
        UnitRecord(orphan_unit, (UnitFacetRef(
            FacetType.TASK, task_b, 1.0, LinkStatus.CONFIRMED, "anchor"),)),
    ]
    facets = [
        WorkFacet(FacetType.TASK, task_a, "German practice", None),
        WorkFacet(FacetType.TASK, task_b, "Budget review", None),
    ]
    edges = [GoalEdge(served_unit, served_goal_id, 0.9, LinkStatus.CONFIRMED, "commitment")]

    def _goal(gid, name):
        return Goal(
            id=gid, tenant_id=UUID(_TENANT), jurisdiction="eu-west", name=name,
            mode=GoalMode.PROGRESSIVE, control=ControlAxis.SELF, subject=Subject.SELF,
            lever_commitment_id=cid,
            ladder=LevelLadder(levels=("A1", "A2"), current_target_level="A2"),
        )

    client = _client(
        _FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()),
        goal_graph=_FakeGoalGraphForAssessment(
            [_goal(served_goal_id, "German"), _goal(neglected_goal_id, "Marathon")]
        ),
        unit_graph=_FakeUnitGraph(records, goal_edges=edges),
        facet_source=_FakeFacetSource(facets),
    )
    res = client.get("/api/v1/daily-driver/assessment")
    assert res.status_code == 200, res.text
    body = res.json()
    # One goal covered → coverage exists → orphan emitted; the unlinked goal is
    # uncovered (D171), not "neglected".
    assert body["coverage"]["has_coverage"] is True
    assert body["coverage"]["goals_covered"] == 1
    assert [o["unit_id"] for o in body["orphan_work"]] == [str(orphan_unit)]
    assert [g["outcome_id"] for g in body["uncovered_goals"]] == [str(neglected_goal_id)]


def test_assessment_route_empty_when_seams_unwired() -> None:
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()))
    res = client.get("/api/v1/daily-driver/assessment")
    assert res.status_code == 200
    body = res.json()
    assert body["coverage"]["has_coverage"] is False
    assert body["uncovered_goals"] == []
    assert body["orphan_work"] == []


def test_suggestions_route_returns_goal_served_missing_facet_suggestions() -> None:
    from contexts.daily_driver.domain.goal_assessment import GoalEdge
    from contexts.daily_driver.domain.work_unit import (
        FacetType, LinkStatus, WorkFacet,
    )
    from contexts.daily_driver.ports.unit_graph import UnitFacetRef, UnitRecord

    served_unit, orphan_unit = uuid4(), uuid4()
    served_task, orphan_task = uuid4(), uuid4()
    goal_id = uuid4()
    records = [
        UnitRecord(served_unit, (UnitFacetRef(
            FacetType.TASK, served_task, 1.0, LinkStatus.CONFIRMED, "anchor"),)),
        UnitRecord(orphan_unit, (UnitFacetRef(
            FacetType.TASK, orphan_task, 1.0, LinkStatus.CONFIRMED, "anchor"),)),
    ]
    due = datetime(2026, 6, 12, tzinfo=timezone.utc)
    facets = [
        WorkFacet(FacetType.TASK, served_task, "Ship Q3 report", due),
        WorkFacet(FacetType.TASK, orphan_task, "Random errand", due),
    ]
    # Only the served unit has a SERVES edge → only it can be suggested.
    edges = [GoalEdge(served_unit, goal_id, 0.9, LinkStatus.CONFIRMED, "commitment")]

    # The served goal is PROGRESSIVE (non-homeostatic), so the D196 relevance
    # gate does not fire — the served unit keeps its block suggestion.
    from contexts.daily_driver.domain.goal import (
        ControlAxis, Goal, GoalMode, LevelLadder, Subject,
    )

    progressive_goal = Goal(
        id=goal_id, tenant_id=UUID(_TENANT), jurisdiction="eu-west",
        name="Learn German", mode=GoalMode.PROGRESSIVE,
        control=ControlAxis.SELF, subject=Subject.SELF,
        lever_commitment_id=uuid4(),
        ladder=LevelLadder(levels=("A1", "A2"), current_target_level="A2"),
    )

    client = _client(
        _FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()),
        unit_graph=_FakeUnitGraph(records, goal_edges=edges),
        facet_source=_FakeFacetSource(facets),
        goal_graph=_FakeGoalGraph(progressive_goal),
    )
    res = client.get("/api/v1/daily-driver/suggestions")
    assert res.status_code == 200, res.text
    body = res.json()
    assert [s["unit_id"] for s in body] == [str(served_unit)]
    assert body[0]["kind"] == "block"


def test_suggestions_route_gates_a_homeostatic_served_unit_D196() -> None:
    """D196 at the route: a unit whose served outcome is homeostatic (a
    maintenance rhythm, e.g. a medication dose) produces no suggestion — the
    live Health-regimen flood reads zero."""
    from contexts.daily_driver.domain.goal import (
        ControlAxis, Goal, GoalMode, Subject,
    )
    from contexts.daily_driver.domain.goal_assessment import GoalEdge
    from contexts.daily_driver.domain.work_unit import (
        FacetType, LinkStatus, WorkFacet,
    )
    from contexts.daily_driver.ports.unit_graph import UnitFacetRef, UnitRecord

    served_unit, served_task, goal_id = uuid4(), uuid4(), uuid4()
    records = [
        UnitRecord(served_unit, (UnitFacetRef(
            FacetType.TASK, served_task, 1.0, LinkStatus.CONFIRMED, "anchor"),)),
    ]
    due = datetime(2026, 6, 12, tzinfo=timezone.utc)
    facets = [WorkFacet(FacetType.TASK, served_task, "Lansoprazole", due)]
    edges = [GoalEdge(served_unit, goal_id, 0.9, LinkStatus.CONFIRMED, "commitment")]

    homeostatic_goal = Goal(
        id=goal_id, tenant_id=UUID(_TENANT), jurisdiction="eu-west",
        name="Health regimen", mode=GoalMode.HOMEOSTATIC,
        control=ControlAxis.SELF, subject=Subject.SELF,
        lever_commitment_id=uuid4(),
    )

    client = _client(
        _FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()),
        unit_graph=_FakeUnitGraph(records, goal_edges=edges),
        facet_source=_FakeFacetSource(facets),
        goal_graph=_FakeGoalGraph(homeostatic_goal),
    )
    res = client.get("/api/v1/daily-driver/suggestions")
    assert res.status_code == 200, res.text
    assert res.json() == []


def test_suggestions_route_empty_when_seams_unwired() -> None:
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()))
    res = client.get("/api/v1/daily-driver/suggestions")
    assert res.status_code == 200
    assert res.json() == []


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


# --- D214: close / reopen an opportunity (the closed state) -------------------

class _FakeOppGraph:
    """A goal graph that records close/reopen calls (S103n, D214)."""

    def __init__(self, *, known: set | None = None) -> None:
        self.known = known if known is not None else {_OPP}
        self.closed: dict = {}
        self.reopened: list = []
        self.confirmed: list = []
        self.rejected: list = []
        self.restaged: list = []

    async def close_opportunity(self, *, tenant_context, opportunity_id, closed_reason):
        if opportunity_id not in self.known:
            return False
        self.closed[opportunity_id] = closed_reason
        return True

    async def reopen_opportunity(self, *, tenant_context, opportunity_id):
        if opportunity_id not in self.known:
            return False
        self.reopened.append(opportunity_id)
        return True

    async def confirm_opportunity(self, *, tenant_context, opportunity_id):
        if opportunity_id not in self.known:
            return False
        self.confirmed.append(opportunity_id)
        return True

    async def delete_opportunity(self, *, tenant_context, opportunity_id):
        if opportunity_id not in self.known:
            return False
        self.rejected.append(opportunity_id)
        return True

    async def set_opportunity_gate(self, *, tenant_context, opportunity_id, current_gate_id):
        if opportunity_id not in self.known:
            return False
        self.restaged.append((opportunity_id, current_gate_id))
        return True


_OPP = uuid4()


def test_close_opportunity_requires_a_valid_reason() -> None:
    # AC1: a close is rejected unless the reason is one of the five types.
    graph = _FakeOppGraph()
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()), goal_graph=graph)
    res = client.post(
        f"/api/v1/daily-driver/cdd/opportunity/{_OPP}/close",
        json={"reason": "ghosted-them"},
    )
    assert res.status_code == 422, res.text
    assert graph.closed == {}  # nothing written on an invalid reason


def test_close_opportunity_with_valid_reason_persists() -> None:
    graph = _FakeOppGraph()
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()), goal_graph=graph)
    res = client.post(
        f"/api/v1/daily-driver/cdd/opportunity/{_OPP}/close",
        json={"reason": "rejected"},
    )
    assert res.status_code == 204, res.text
    assert graph.closed[_OPP] == "rejected"


def test_close_unknown_opportunity_404() -> None:
    graph = _FakeOppGraph(known=set())
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()), goal_graph=graph)
    res = client.post(
        f"/api/v1/daily-driver/cdd/opportunity/{_OPP}/close",
        json={"reason": "won"},
    )
    assert res.status_code == 404, res.text


def test_reopen_opportunity_route() -> None:
    graph = _FakeOppGraph()
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()), goal_graph=graph)
    res = client.post(f"/api/v1/daily-driver/cdd/opportunity/{_OPP}/reopen")
    assert res.status_code == 204, res.text
    assert graph.reopened == [_OPP]


def test_confirm_opportunity_route() -> None:
    # D215: confirm a system-suggested opportunity -> user_authored.
    graph = _FakeOppGraph()
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()), goal_graph=graph)
    res = client.post(f"/api/v1/daily-driver/cdd/opportunity/{_OPP}/confirm")
    assert res.status_code == 204, res.text
    assert graph.confirmed == [_OPP]


def test_reject_opportunity_route_deletes_the_cluster() -> None:
    graph = _FakeOppGraph()
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()), goal_graph=graph)
    res = client.post(f"/api/v1/daily-driver/cdd/opportunity/{_OPP}/reject")
    assert res.status_code == 204, res.text
    assert graph.rejected == [_OPP]


def test_confirm_unknown_opportunity_404() -> None:
    graph = _FakeOppGraph(known=set())
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()), goal_graph=graph)
    res = client.post(f"/api/v1/daily-driver/cdd/opportunity/{_OPP}/confirm")
    assert res.status_code == 404, res.text


# --- D216: the how-am-i-doing assessment endpoint ---------------------------

class _AssessGoalGraph:
    """A goal graph returning a GoalCddView for the assessment read (D216)."""

    def __init__(self, view) -> None:
        self._view = view

    async def read_goal_cdd(self, *, tenant_context, outcome_id):
        return self._view


def _assess_view():
    from contexts.daily_driver.domain.cdd import (
        DispositionCounts, GateView, GoalCddView, OpportunityView,
        ProofState, ProvenanceOrigin,
    )

    apply_g, screen_g = uuid4(), uuid4()
    gates = (
        GateView(gate_id=apply_g, name="Apply", gate_order=3, local_outcome="",
                 local_goal="", provenance_origin=ProvenanceOrigin.LLM_DRAFTED,
                 proof_state=ProofState.PENDING),
        GateView(gate_id=screen_g, name="Screening", gate_order=4, local_outcome="",
                 local_goal="", provenance_origin=ProvenanceOrigin.LLM_DRAFTED,
                 proof_state=ProofState.PENDING),
    )

    def opp(prov, status, reason=None, gate=None):
        return OpportunityView(
            opportunity_id=uuid4(), name="Co", current_gate_id=gate, unit_count=2,
            provenance_origin=prov, proof_state=ProofState.PENDING,
            status=status, closed_reason=reason,
        )

    opps = (
        opp(ProvenanceOrigin.SYSTEM_SUGGESTED, "closed", "rejected"),
        opp(ProvenanceOrigin.USER_AUTHORED, "closed", "rejected", screen_g),  # interviewed
        opp(ProvenanceOrigin.SYSTEM_SUGGESTED, "live"),
    )
    return GoalCddView(
        outcome_id=uuid4(), expected_outcome="Secure a great-fit role",
        elements=(), edges=(), gates=gates, opportunities=opps,
        disposition=DispositionCounts(moat=166, pipeline=102, market=96, parked=247),
    )


def test_assessment_route_reads_label_independent_verdict() -> None:
    client = _client(
        _FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()),
        goal_graph=_AssessGoalGraph(_assess_view()),
    )
    res = client.get(f"/api/v1/daily-driver/cdd/assessment/{uuid4()}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["verdict_label"] == "pipeline empty"
    assert body["confirmed_live"] == 0 and body["offers"] == 0
    assert body["interviewed"] == 1  # the Screening opp, gate beyond Apply
    assert body["one_touch_volume"] == 102 and body["activity"] == 166
    assert body["split_proof_dependent"] is True  # a suggested closed opp exists
    assert "targeting" in body["move"]


def test_restage_opportunity_writes_the_gate() -> None:
    # D217: drag-to-re-stage writes the opportunity's gate (the proof action).
    graph = _FakeOppGraph()
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()), goal_graph=graph)
    gate = uuid4()
    res = client.post(
        f"/api/v1/daily-driver/cdd/opportunity/{_OPP}/stage",
        json={"gate_id": str(gate)},
    )
    assert res.status_code == 204, res.text
    assert graph.restaged == [(_OPP, gate)]


def test_restage_to_unplaced_clears_the_gate() -> None:
    graph = _FakeOppGraph()
    client = _client(_FakeCommitmentRepo(), _FakeDayRepo(), _FakeOpenCases(()), goal_graph=graph)
    res = client.post(f"/api/v1/daily-driver/cdd/opportunity/{_OPP}/stage", json={"gate_id": None})
    assert res.status_code == 204, res.text
    assert graph.restaged == [(_OPP, None)]


def test_app_surface_served_with_no_store_so_fixes_are_never_cached() -> None:
    """The operator surface is a single self-contained HTML whose inline JS
    changes every deploy; ``FileResponse`` alone would let a browser hold a
    stale copy and read every fix as "no change" (the S103s relink loop). The
    ``/app`` route must send ``Cache-Control: no-store`` so the current bytes
    are always fetched."""
    app = FastAPI()
    app.include_router(daily_driver_router.ui_router)
    res = TestClient(app).get("/app")
    assert res.status_code == 200
    assert "no-store" in res.headers.get("cache-control", "")
