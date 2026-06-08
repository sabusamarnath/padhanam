"""Application-layer tests for the daily-driver use cases (D157).

In-memory fakes for the three ports exercise the aggregation, the
authorisation boundary, and the completion-clears-overdue loop without a
database.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.daily_driver.application import (
    create_commitment,
    list_today,
    log_commitment_completion,
    mark_item_done,
    record_observed_outcome,
    set_today_order,
)
from contexts.daily_driver.domain.commitment import (
    Commitment,
    CommitmentActivity,
    CommitmentCompletion,
    OutcomeStatus,
)
from contexts.daily_driver.domain.day import DayItemState, item_key
from contexts.daily_driver.domain.today_item import (
    CalendarToday,
    ItemKind,
    ItemStatus,
    OpenCase,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import (
    AuthorisationDenied,
    ROLE_OPERATOR,
    authorisations_for_roles,
)

_TENANT = "00000000-0000-4000-8000-00000000a001"


def _actor(*, authorised: bool = True) -> ActorContext:
    # An unauthorised actor still has a (non-empty) role, but one that
    # grants no daily-driver permission — exercising the use-case-boundary
    # authorisation check rather than the ActorContext non-empty-role guard.
    roles = frozenset({ROLE_OPERATOR}) if authorised else frozenset({"viewer"})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


class FakeCommitmentRepository:
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
        existing = self.commitments.get(commitment_id)
        if existing is None:
            return None
        from dataclasses import replace

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
            times = [
                comp.completed_at
                for comp in self.completions
                if comp.commitment_id == c.id
            ]
            out.append(CommitmentActivity(c, max(times) if times else None))
        return tuple(out)


class FakeDayRepository:
    def __init__(self) -> None:
        self.states: dict[str, DayItemState] = {}

    async def get_states(self, *, tenant_context, user_id, day_date):
        return tuple(self.states.values())

    async def set_positions(self, *, tenant_context, user_id, day_date, ordered_keys):
        for pos, (kind, item_id) in enumerate(ordered_keys):
            k = item_key(kind, item_id)
            prev = self.states.get(k)
            self.states[k] = DayItemState(
                kind=kind,
                item_id=item_id,
                position=pos,
                done=prev.done if prev else False,
            )

    async def set_done(self, *, tenant_context, user_id, day_date, kind, item_id, done):
        k = item_key(kind, item_id)
        prev = self.states.get(k)
        self.states[k] = DayItemState(
            kind=kind,
            item_id=item_id,
            position=prev.position if prev else None,
            done=done,
        )


class FakeOpenCasesReader:
    def __init__(self, cases: tuple[OpenCase, ...]) -> None:
        self._cases = cases

    async def list_open_cases(self, *, actor):
        return self._cases


class FakeCalendarEventsReader:
    def __init__(self, events: tuple[CalendarToday, ...]) -> None:
        self._events = events
        self.calls: list[date] = []

    async def list_today_events(self, *, actor, day_date):
        self.calls.append(day_date)
        return self._events


def test_create_commitment_persists_and_returns() -> None:
    repo = FakeCommitmentRepository()
    commitment = asyncio.run(
        create_commitment(
            repository=repo,
            actor=_actor(),
            name="Weekly 1:1",
            expected_interval_days=7,
        )
    )
    assert commitment.id in repo.commitments
    assert commitment.tenant_id == UUID(_TENANT)
    assert commitment.authored_by_user_id == "operator-001"


def test_create_commitment_captures_expected_outcome() -> None:
    repo = FakeCommitmentRepository()
    commitment = asyncio.run(
        create_commitment(
            repository=repo,
            actor=_actor(),
            name="Weekly 1:1",
            expected_interval_days=7,
            expected_outcome="reports feel supported",
        )
    )
    assert commitment.expected_outcome == "reports feel supported"
    assert repo.commitments[commitment.id].expected_outcome == (
        "reports feel supported"
    )


def test_record_observed_outcome_sets_status_and_returns_updated() -> None:
    repo = FakeCommitmentRepository()
    c = _seed_overdue(repo)
    updated = asyncio.run(
        record_observed_outcome(
            repository=repo,
            actor=_actor(),
            commitment_id=c.id,
            observed_outcome="only partly happened",
            outcome_status=OutcomeStatus.PARTIAL,
        )
    )
    assert updated is not None
    assert updated.observed_outcome == "only partly happened"
    assert updated.outcome_status is OutcomeStatus.PARTIAL
    assert updated.observed_at is not None


def test_record_observed_outcome_requires_authorisation() -> None:
    repo = FakeCommitmentRepository()
    c = _seed_overdue(repo)
    with pytest.raises(AuthorisationDenied):
        asyncio.run(
            record_observed_outcome(
                repository=repo,
                actor=_actor(authorised=False),
                commitment_id=c.id,
                observed_outcome="x",
                outcome_status=OutcomeStatus.MET,
            )
        )


def test_record_observed_outcome_unknown_returns_none() -> None:
    repo = FakeCommitmentRepository()
    result = asyncio.run(
        record_observed_outcome(
            repository=repo,
            actor=_actor(),
            commitment_id=uuid4(),
            observed_outcome=None,
            outcome_status=OutcomeStatus.DROPPED,
        )
    )
    assert result is None


def test_list_today_flags_quiet_commitment_as_drop_candidate() -> None:
    repo = FakeCommitmentRepository()
    _seed_overdue(repo)  # created 2026-05-01 → quiet well past 21 days
    view = asyncio.run(
        list_today(
            open_cases_reader=FakeOpenCasesReader(()),
            commitment_repository=repo,
            day_repository=FakeDayRepository(),
            actor=_actor(),
            drop_candidate_quiet_days=21,
        )
    )
    assert view.items[0].drop_candidate is True


def test_dropping_clears_the_drop_candidate_flag() -> None:
    repo = FakeCommitmentRepository()
    c = _seed_overdue(repo)
    asyncio.run(
        record_observed_outcome(
            repository=repo,
            actor=_actor(),
            commitment_id=c.id,
            observed_outcome=None,
            outcome_status=OutcomeStatus.DROPPED,
        )
    )
    view = asyncio.run(
        list_today(
            open_cases_reader=FakeOpenCasesReader(()),
            commitment_repository=repo,
            day_repository=FakeDayRepository(),
            actor=_actor(),
            drop_candidate_quiet_days=21,
        )
    )
    assert view.items[0].drop_candidate is False
    assert view.items[0].outcome_status == "dropped"


def test_create_commitment_requires_authorisation() -> None:
    repo = FakeCommitmentRepository()
    with pytest.raises(AuthorisationDenied):
        asyncio.run(
            create_commitment(
                repository=repo,
                actor=_actor(authorised=False),
                name="Weekly 1:1",
                expected_interval_days=7,
            )
        )


def _seed_overdue(repo: FakeCommitmentRepository) -> Commitment:
    c = Commitment(
        id=uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        name="Weekly review",
        expected_interval_days=7,
        authored_by_user_id="operator-001",
        created_at=datetime.now(timezone.utc).replace(year=2026, month=5, day=1),
    )
    repo.commitments[c.id] = c
    return c


def test_list_today_surfaces_overdue_first() -> None:
    repo = FakeCommitmentRepository()
    overdue = _seed_overdue(repo)
    case = OpenCase(case_id=uuid4(), title="Launch plan", created_at=datetime.now(timezone.utc))
    view = asyncio.run(
        list_today(
            open_cases_reader=FakeOpenCasesReader((case,)),
            commitment_repository=repo,
            day_repository=FakeDayRepository(),
            actor=_actor(),
        )
    )
    assert view.items[0].kind == ItemKind.COMMITMENT
    assert view.items[0].status == ItemStatus.BEHIND
    assert overdue.name == view.items[0].title


def test_list_today_includes_calendar_events_when_reader_wired() -> None:
    repo = FakeCommitmentRepository()
    now = datetime.now(timezone.utc)
    event = CalendarToday(
        meeting_id=uuid4(),
        google_event_id="evt-1",
        title="Board call",
        start_at=now.replace(hour=23, minute=0),
        end_at=None,
        domain="work",
    )
    reader = FakeCalendarEventsReader((event,))
    view = asyncio.run(
        list_today(
            open_cases_reader=FakeOpenCasesReader(()),
            commitment_repository=repo,
            day_repository=FakeDayRepository(),
            actor=_actor(),
            calendar_events_reader=reader,
        )
    )
    cal_items = [i for i in view.items if i.kind == ItemKind.CALENDAR]
    assert len(cal_items) == 1
    assert cal_items[0].title == "Board call"
    assert cal_items[0].domain == "work"
    # the reader is scoped to the current UTC day
    assert reader.calls == [now.date()]


def test_list_today_without_calendar_reader_is_cases_and_commitments() -> None:
    repo = FakeCommitmentRepository()
    case = OpenCase(case_id=uuid4(), title="Launch plan", created_at=datetime.now(timezone.utc))
    view = asyncio.run(
        list_today(
            open_cases_reader=FakeOpenCasesReader((case,)),
            commitment_repository=repo,
            day_repository=FakeDayRepository(),
            actor=_actor(),
        )
    )
    assert all(i.kind != ItemKind.CALENDAR for i in view.items)
    assert any(i.kind == ItemKind.CASE for i in view.items)


def test_logging_completion_clears_overdue() -> None:
    repo = FakeCommitmentRepository()
    overdue = _seed_overdue(repo)
    completion = asyncio.run(
        log_commitment_completion(
            repository=repo, actor=_actor(), commitment_id=overdue.id
        )
    )
    assert completion is not None
    view = asyncio.run(
        list_today(
            open_cases_reader=FakeOpenCasesReader(()),
            commitment_repository=repo,
            day_repository=FakeDayRepository(),
            actor=_actor(),
        )
    )
    assert view.items[0].status == ItemStatus.ON_TRACK


def test_logging_completion_unknown_commitment_returns_none() -> None:
    repo = FakeCommitmentRepository()
    result = asyncio.run(
        log_commitment_completion(
            repository=repo, actor=_actor(), commitment_id=uuid4()
        )
    )
    assert result is None


def test_mark_done_overlays_and_persists() -> None:
    repo = FakeCommitmentRepository()
    day = FakeDayRepository()
    case = OpenCase(case_id=uuid4(), title="Launch plan", created_at=datetime.now(timezone.utc))
    asyncio.run(
        mark_item_done(
            day_repository=day,
            actor=_actor(),
            kind=ItemKind.CASE,
            item_id=case.case_id,
            done=True,
        )
    )
    view = asyncio.run(
        list_today(
            open_cases_reader=FakeOpenCasesReader((case,)),
            commitment_repository=repo,
            day_repository=day,
            actor=_actor(),
        )
    )
    # D175: the done case moves to the history slice, off the live list.
    assert view.history[0].status == ItemStatus.DONE
    assert not view.items


def test_set_order_persisted_and_applied() -> None:
    repo = FakeCommitmentRepository()
    overdue = _seed_overdue(repo)
    day = FakeDayRepository()
    case = OpenCase(case_id=uuid4(), title="Launch plan", created_at=datetime.now(timezone.utc))
    # pin the case ahead of the (behind) commitment
    asyncio.run(
        set_today_order(
            day_repository=day,
            actor=_actor(),
            ordered_keys=(
                (ItemKind.CASE, case.case_id),
                (ItemKind.COMMITMENT, overdue.id),
            ),
        )
    )
    view = asyncio.run(
        list_today(
            open_cases_reader=FakeOpenCasesReader((case,)),
            commitment_repository=repo,
            day_repository=day,
            actor=_actor(),
        )
    )
    assert view.items[0].kind == ItemKind.CASE
    assert view.items[1].kind == ItemKind.COMMITMENT
