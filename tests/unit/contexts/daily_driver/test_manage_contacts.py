"""S103u/D222: the contact proof + management use cases — validation and the
user-authored writes over a fake GoalGraphPort."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest

from contexts.daily_driver.application.manage_contacts import (
    ContactValidationError,
    add_contact,
    confirm_contact,
    enrich_contact,
    reject_contact,
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


class _FakeGraph:
    def __init__(self):
        self.created = None
        self.enriched = None

    async def create_contact(self, *, tenant_context, contact_id, name, company,
                             degree, strength, reachability, capture_source):
        self.created = dict(
            tenant_id=tenant_context.tenant_id, contact_id=contact_id, name=name,
            company=company, degree=degree, strength=strength,
            reachability=reachability, capture_source=capture_source,
        )

    async def confirm_contact(self, *, tenant_context, contact_id):
        return True

    async def enrich_contact(self, *, tenant_context, contact_id, degree, strength,
                             reachability):
        self.enriched = dict(contact_id=contact_id, degree=degree, strength=strength,
                             reachability=reachability)
        return True

    async def reject_contact(self, *, tenant_context, contact_id):
        return True


def test_add_contact_writes_user_authored_with_capture_source():
    g = _FakeGraph()

    async def run():
        return await add_contact(
            goal_graph=g, actor=_actor(), name="Jane Doe", company="Acme",
            degree="first", strength="close", reachability="easy",
            capture_source="linkedin",
        )

    cid = asyncio.run(run())
    assert isinstance(cid, UUID)
    assert g.created["name"] == "Jane Doe"
    assert g.created["company"] == "Acme"
    assert g.created["capture_source"] == "linkedin"
    assert g.created["tenant_id"] == _TENANT


def test_add_contact_blank_company_becomes_none():
    g = _FakeGraph()

    async def run():
        await add_contact(goal_graph=g, actor=_actor(), name="X", company="   ")

    asyncio.run(run())
    assert g.created["company"] is None
    assert g.created["capture_source"] == "manual"   # default


@pytest.mark.parametrize("kwargs", [
    dict(name="X", degree="cousin"),
    dict(name="X", strength="lukewarm"),
    dict(name="X", reachability="teleport"),
    dict(name="X", capture_source="carrier-pigeon"),
    dict(name="  "),
])
def test_add_contact_rejects_bad_vocabulary(kwargs):
    g = _FakeGraph()

    async def run():
        await add_contact(goal_graph=g, actor=_actor(), company="Acme", **kwargs)

    with pytest.raises(ContactValidationError):
        asyncio.run(run())
    assert g.created is None


def test_enrich_validates_and_writes():
    g = _FakeGraph()
    cid = uuid4()

    async def run():
        return await enrich_contact(
            goal_graph=g, actor=_actor(), contact_id=cid, degree="second",
            strength="medium", reachability=None,
        )

    assert asyncio.run(run()) is True
    assert g.enriched["degree"] == "second" and g.enriched["strength"] == "medium"


def test_enrich_rejects_bad_vocabulary():
    g = _FakeGraph()

    async def run():
        await enrich_contact(goal_graph=g, actor=_actor(), contact_id=uuid4(),
                             degree=None, strength="strongish", reachability=None)

    with pytest.raises(ContactValidationError):
        asyncio.run(run())
    assert g.enriched is None


def test_confirm_and_reject_delegate():
    g = _FakeGraph()
    cid = uuid4()
    assert asyncio.run(confirm_contact(goal_graph=g, actor=_actor(), contact_id=cid)) is True
    assert asyncio.run(reject_contact(goal_graph=g, actor=_actor(), contact_id=cid)) is True
