"""S103w/D229: the opportunity activity history — the event, the log use case
(including the field-touch), and the union read."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.daily_driver.application.activity import (
    ActivityError,
    list_opportunity_activity,
    log_opportunity_activity,
)
from contexts.daily_driver.application.audit_events import (
    ACTION_OPPORTUNITY_ACTIVITY,
    ACTION_WARMING_STEP,
    opportunity_activity_event,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000d001"


def _actor():
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=TenantContext(_TENANT, "eu-west", _TENANT),
        actor_id="op", role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def test_activity_event_shape():
    ev = opportunity_activity_event(
        tenant_context=_actor().tenant_context, actor="op", opportunity_id=uuid4(),
        kind="call", note="spoke to HM", touches_field="champion",
    )
    assert ev.action_verb == ACTION_OPPORTUNITY_ACTIVITY
    assert ev.resource_type == "opportunity"
    assert ev.after_state == {"kind": "call", "note": "spoke to HM", "touches_field": "champion"}


class _FakePort:
    def __init__(self):
        self.emitted = []

    async def emit(self, event):
        self.emitted.append(event)
        return event


class _FakeGraph:
    def __init__(self):
        self.touched = None

    async def set_qualification_field(self, *, tenant_context, opportunity_id,
                                      field_key, value, touch_only=False):
        self.touched = (field_key, value, touch_only)
        return True


def test_log_activity_emits_and_touches_the_named_field():
    port, graph = _FakePort(), _FakeGraph()

    async def run():
        await log_opportunity_activity(
            goal_graph=graph, actor=_actor(), opportunity_id=uuid4(),
            kind="call", note="", touches_field="champion", audit_port=port,
        )

    asyncio.run(run())
    assert len(port.emitted) == 1
    assert port.emitted[0].action_verb == ACTION_OPPORTUNITY_ACTIVITY
    # naming a field bumps its last_touched (a touch_only write)
    assert graph.touched == ("champion", None, True)


def test_log_activity_without_touch_does_not_write_qualification():
    port, graph = _FakePort(), _FakeGraph()

    async def run():
        await log_opportunity_activity(
            goal_graph=graph, actor=_actor(), opportunity_id=uuid4(),
            kind="email", audit_port=port,
        )

    asyncio.run(run())
    assert len(port.emitted) == 1 and graph.touched is None


@pytest.mark.parametrize("kw", [
    dict(kind="   "),
    dict(kind="call", touches_field="vibes"),
])
def test_log_activity_validates(kw):
    port, graph = _FakePort(), _FakeGraph()

    async def run():
        await log_opportunity_activity(
            goal_graph=graph, actor=_actor(), opportunity_id=uuid4(),
            audit_port=port, **kw,
        )

    with pytest.raises(ActivityError):
        asyncio.run(run())
    assert port.emitted == []


class _Rec:
    def __init__(self, verb, kind, touches=""):
        self.action_verb = verb
        self.after_state = {"kind": kind, "note": "", "touches_field": touches}
        self.timestamp = datetime(2026, 7, 1, tzinfo=timezone.utc)
        self.actor = "op"


class _Page:
    def __init__(self, events):
        self.events = events


class _FakeReader:
    def __init__(self):
        self.filters = None

    async def list_audit_events_with_filters(self, *, destination, filters, cursor,
                                             page_size, tenant_context):
        self.filters = filters
        return _Page((
            _Rec(ACTION_OPPORTUNITY_ACTIVITY, "call", "champion"),
            _Rec(ACTION_WARMING_STEP, "intro_requested"),
        ))


def test_list_activity_is_the_union_of_both_verbs():
    reader = _FakeReader()
    oid = uuid4()

    async def run():
        return await list_opportunity_activity(
            actor=_actor(), opportunity_id=oid, audit_reader=reader,
        )

    entries = asyncio.run(run())
    # the read is scoped to the opportunity + BOTH verbs
    assert reader.filters.resource_type == "opportunity"
    assert reader.filters.resource_id == str(oid)
    assert set(reader.filters.action_verbs) == {ACTION_OPPORTUNITY_ACTIVITY, ACTION_WARMING_STEP}
    assert len(entries) == 2
    assert entries[0].touches_field == "champion"
