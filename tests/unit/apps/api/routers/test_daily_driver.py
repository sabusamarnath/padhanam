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


def _client(commit_repo, day_repo, open_cases) -> TestClient:
    app = FastAPI()
    app.include_router(daily_driver_router.router)
    app.state.daily_driver_commitment_repository = commit_repo
    app.state.daily_driver_day_repository = day_repo
    app.state.daily_driver_open_cases_reader = open_cases
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
