"""S103w/D228-D229: the stage-aware qualification model — activation, the people
fields from contact roles, and stage-relative freshness."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.daily_driver.application.qualification import (
    QualificationError,
    _role_by_field,
    _stale,
    set_qualification_field,
)
from contexts.daily_driver.domain.contacts import ContactView
from contexts.daily_driver.domain.qualification import (
    ACTIVATION,
    QUAL_FIELDS,
    build_qualification_base,
    field_active_at_stage,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

_NOW = datetime(2026, 7, 2, tzinfo=timezone.utc)
_TENANT = "00000000-0000-4000-8000-00000000d001"


def _actor():
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=TenantContext(_TENANT, "eu-west", _TENANT),
        actor_id="op", role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def test_eight_fields_and_the_activation_map():
    assert len(QUAL_FIELDS) == 8
    assert field_active_at_stage("vetting_checks", "Offer")
    assert not field_active_at_stage("vetting_checks", "Screening")
    assert field_active_at_stage("champion", "Screening")
    assert field_active_at_stage("role_open", "Lead")
    # every field is active at exactly one mapped stage
    active_keys = set()
    for keys in ACTIVATION.values():
        active_keys |= keys
    assert active_keys == {k for k, _ in QUAL_FIELDS}


def test_stage_relative_freshness_flags_only_active_fields():
    # vetting silent since June 1 (>14d): stale at Offer (active), quiet at Screening.
    props = {"q_vetting_checks": "BGV pending", "q_vetting_checks_ts": "2026-06-01T00:00:00+00:00"}
    at_offer = {f.key: f for f in build_qualification_base(qual_props=props, stage="Offer")}
    at_screen = {f.key: f for f in build_qualification_base(qual_props=props, stage="Screening")}
    assert _stale(at_offer["vetting_checks"], _NOW, 14) == "stale"
    assert _stale(at_screen["vetting_checks"], _NOW, 14) is None  # not active -> quiet


def test_fresh_active_field_is_not_stale():
    props = {"q_role_open": "backfill", "q_role_open_ts": "2026-07-01T00:00:00+00:00"}
    f = {x.key: x for x in build_qualification_base(qual_props=props, stage="Lead")}["role_open"]
    assert f.active and _stale(f, _NOW, 14) is None  # only 1 day silent


def test_empty_active_field_carries_no_risk():
    f = {x.key: x for x in build_qualification_base(qual_props={}, stage="Lead")}["role_open"]
    assert f.active and f.value is None and _stale(f, _NOW, 14) is None


def test_people_fields_fall_back_to_role_typed_contacts():
    champ = ContactView(uuid4(), "Jane", "j@acme.example", "Acme", None, None, None, "email", "user_authored", process_role="champion")
    dm = ContactView(uuid4(), "Sam", "s@acme.example", "Acme", None, None, None, "email", "user_authored", process_role="decision_maker")
    rbf = _role_by_field("Acme", (champ, dm))
    assert rbf == {"champion": "Jane", "decision_maker": "Sam"}
    fields = {f.key: f for f in build_qualification_base(qual_props={}, stage="Screening", role_by_field=rbf)}
    assert fields["champion"].value == "Jane" and fields["champion"].from_contact
    assert fields["decision_maker"].value == "Sam"


def test_stored_value_overrides_the_role_fallback():
    props = {"q_champion": "Priya", "q_champion_ts": "2026-07-01T00:00:00+00:00"}
    rbf = {"champion": "Jane"}
    f = {x.key: x for x in build_qualification_base(qual_props=props, stage="Screening", role_by_field=rbf)}["champion"]
    assert f.value == "Priya" and not f.from_contact  # the authored value wins


class _FakeGraph:
    def __init__(self):
        self.set = None

    async def set_qualification_field(self, *, tenant_context, opportunity_id,
                                      field_key, value, touch_only=False):
        self.set = (field_key, value, touch_only)
        return True


def test_set_qualification_rejects_unknown_field():
    g = _FakeGraph()

    async def run():
        await set_qualification_field(goal_graph=g, actor=_actor(),
                                      opportunity_id=uuid4(), field_key="vibes", value="x")

    with pytest.raises(QualificationError):
        asyncio.run(run())
    assert g.set is None


def test_set_qualification_writes_a_known_field():
    g = _FakeGraph()

    async def run():
        return await set_qualification_field(goal_graph=g, actor=_actor(),
                                             opportunity_id=uuid4(),
                                             field_key="role_open", value=" backfill ")

    assert asyncio.run(run()) is True
    assert g.set == ("role_open", "backfill", False)
