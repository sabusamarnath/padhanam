"""read_act_worklist — the six-source composition + per-source guards (D232).

The pipeline/warming/qualification path (which needs the assessment seams) is
exercised at the router level; here the seams are absent so that path degrades
cleanly, and the commitment / calendar / case mappers are asserted directly.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from contexts.daily_driver.application.read_act_worklist import read_act_worklist
from contexts.daily_driver.domain.commitment import (
    Commitment,
    CommitmentActivity,
    OutcomeStatus,
)
from contexts.daily_driver.domain.today_item import CalendarToday, OpenCase
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000a001"
_NOW = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)


def _actor() -> ActorContext:
    roles = frozenset({"operator"})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001", role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


class _Commit:
    def __init__(self, activities):
        self._activities = activities

    async def list_with_activity(self, *, tenant_context):
        return tuple(self._activities)


class _Cases:
    def __init__(self, cases):
        self._cases = cases

    async def list_open_cases(self, *, actor):
        return tuple(self._cases)


class _Calendar:
    def __init__(self, events):
        self._events = events

    async def list_today_events(self, *, actor, day_date):
        return tuple(self._events)


def _commitment(name, interval, created, *, dropped=False):
    return Commitment(
        id=uuid4(), tenant_id=UUID(_TENANT), jurisdiction="eu-west", name=name,
        expected_interval_days=interval, authored_by_user_id="operator-001",
        created_at=created,
        outcome_status=OutcomeStatus.DROPPED if dropped else None,
    )


def _run(**kw):
    return asyncio.run(read_act_worklist(
        goal_graph=object(), actor=_actor(), now=_NOW,
        unit_graph=None, facet_source=None,  # pipeline path degrades to empty
        **kw,
    ))


def test_overdue_and_ontrack_commitments_get_horizons() -> None:
    overdue = _commitment("Weekly review", 7, _NOW - timedelta(days=20))
    ontrack = _commitment("Monthly report", 30, _NOW - timedelta(days=2))
    items = _run(
        commitment_repository=_Commit(
            [CommitmentActivity(overdue, None), CommitmentActivity(ontrack, None)]
        ),
        open_cases_reader=_Cases([]),
    )
    by_name = {i.subject: i for i in items}
    assert by_name["Weekly review"].due_in_days == 7 - 20  # overdue
    assert "Overdue by 13 days" in by_name["Weekly review"].action
    assert by_name["Monthly report"].due_in_days == 30 - 2  # upcoming
    assert all(not i.is_opportunity for i in items)


def test_dropped_commitment_is_excluded() -> None:
    dropped = _commitment("Abandoned", 7, _NOW - timedelta(days=40), dropped=True)
    items = _run(
        commitment_repository=_Commit([CommitmentActivity(dropped, None)]),
        open_cases_reader=_Cases([]),
    )
    assert items == ()


def test_cases_and_calendar_are_due_today_non_opportunity() -> None:
    case = OpenCase(case_id=uuid4(), title="Launch plan", created_at=_NOW)
    event = CalendarToday(
        meeting_id=uuid4(), google_event_id="g1", title="Standup",
        start_at=_NOW, end_at=None, domain="work",
    )
    items = _run(
        commitment_repository=_Commit([]),
        open_cases_reader=_Cases([case]),
        calendar_events_reader=_Calendar([event]),
    )
    assert {i.source for i in items} == {"case", "calendar"}
    assert all(i.due_in_days == 0 and not i.is_opportunity for i in items)


def test_pipeline_degrades_when_seams_absent() -> None:
    # unit_graph / facet_source are None (via _run) — the model sources drop out
    # rather than failing the whole worklist.
    items = _run(
        commitment_repository=_Commit([]), open_cases_reader=_Cases([]),
    )
    assert items == ()
