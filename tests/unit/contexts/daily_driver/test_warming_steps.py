"""S103v/D224: warming-step tracking — the event drafter (tenant-bound), the log
use case (validation + emit), and the per-subject faceted read."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.daily_driver.application.audit_events import (
    ACTION_WARMING_STEP,
    warming_step_event,
)
from contexts.daily_driver.application.warming_steps import (
    WarmingStepError,
    list_warming_steps,
    log_warming_step,
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
        actor_id="operator-001", role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def test_warming_step_event_binds_tenant_verb_and_subject():
    cid = uuid4()
    ev = warming_step_event(
        tenant_context=_actor().tenant_context, actor="op", subject_type="contact",
        subject_id=cid, kind="intro_requested", note="asked Jane for a referral",
    )
    assert ev.action_verb == ACTION_WARMING_STEP
    assert ev.resource_type == "contact" and ev.resource_id == str(cid)
    assert ev.tenant_id == _TENANT
    assert ev.after_state["kind"] == "intro_requested"
    assert ev.after_state["note"] == "asked Jane for a referral"


class _FakePort:
    def __init__(self):
        self.emitted = []

    async def emit(self, event):
        self.emitted.append(event)
        return event


def test_log_warming_step_emits_via_audit_port():
    port = _FakePort()

    async def run():
        await log_warming_step(
            actor=_actor(), subject_type="opportunity", subject_id=uuid4(),
            kind="follow_up_sent", note="pinged", audit_port=port,
        )

    asyncio.run(run())
    assert len(port.emitted) == 1
    assert port.emitted[0].action_verb == ACTION_WARMING_STEP
    assert port.emitted[0].resource_type == "opportunity"


@pytest.mark.parametrize("kw", [
    dict(subject_type="planet", kind="intro_requested"),
    dict(subject_type="contact", kind="mind_meld"),
])
def test_log_warming_step_rejects_bad_vocabulary(kw):
    port = _FakePort()

    async def run():
        await log_warming_step(actor=_actor(), subject_id=uuid4(), audit_port=port, **kw)

    with pytest.raises(WarmingStepError):
        asyncio.run(run())
    assert port.emitted == []


def test_log_warming_step_without_audit_port_raises():
    async def run():
        await log_warming_step(
            actor=_actor(), subject_type="contact", subject_id=uuid4(),
            kind="intro_requested", audit_port=None,
        )

    with pytest.raises(WarmingStepError):
        asyncio.run(run())


class _FakeRecord:
    def __init__(self, kind):
        self.after_state = {"kind": kind, "note": ""}
        self.timestamp = datetime(2026, 7, 1, tzinfo=timezone.utc)
        self.actor = "op"


class _FakePage:
    def __init__(self, events):
        self.events = events


class _FakeReader:
    def __init__(self):
        self.filters = None

    async def list_audit_events_with_filters(self, *, destination, filters, cursor,
                                             page_size, tenant_context):
        self.filters = filters
        return _FakePage((_FakeRecord("intro_requested"),))


def test_list_warming_steps_filters_by_subject_and_verb():
    reader = _FakeReader()
    sid = uuid4()

    async def run():
        return await list_warming_steps(
            actor=_actor(), subject_type="contact", subject_id=sid, audit_reader=reader,
        )

    steps = asyncio.run(run())
    # the faceted read is scoped to the subject id + type + the warming verb
    assert reader.filters.resource_type == "contact"
    assert reader.filters.resource_id == str(sid)
    assert reader.filters.action_verbs == (ACTION_WARMING_STEP,)
    assert len(steps) == 1 and steps[0].kind == "intro_requested"


def test_list_warming_steps_no_reader_yields_empty():
    async def run():
        return await list_warming_steps(
            actor=_actor(), subject_type="contact", subject_id=uuid4(),
            audit_reader=None,
        )

    assert asyncio.run(run()) == ()
