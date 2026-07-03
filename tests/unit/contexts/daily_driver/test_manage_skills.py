"""Skills-profile management: add (confirmed), confirm, edit, reject, validation
(S103af, D238)."""

from __future__ import annotations

import asyncio

import pytest

from contexts.daily_driver.application.manage_skills import (
    SkillValidationError,
    add_skill_item,
    confirm_skill_item,
    edit_skill_item,
    reject_skill_item,
)
from contexts.daily_driver.domain.cv_extraction import skill_item_id
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000a001"


def _actor() -> ActorContext:
    roles = frozenset({"operator"})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001", role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


class _FakeGraph:
    def __init__(self) -> None:
        self.created: list[tuple] = []
        self.confirmed: list = []
        self.edited: list[tuple] = []
        self.rejected: list = []
        self.match = True

    async def create_skill_item(self, *, tenant_context, item_id, kind, text):
        self.created.append((tenant_context, item_id, kind, text))

    async def confirm_skill_item(self, *, tenant_context, item_id):
        self.confirmed.append(item_id)
        return self.match

    async def edit_skill_item(self, *, tenant_context, item_id, text):
        self.edited.append((item_id, text))
        return self.match

    async def reject_skill_item(self, *, tenant_context, item_id):
        self.rejected.append(item_id)
        return self.match


def test_add_uses_confirmed_create_with_deterministic_id_and_normalized_text() -> None:
    graph = _FakeGraph()
    item_id = asyncio.run(add_skill_item(
        goal_graph=graph, actor=_actor(), kind="skill", text="  Product   strategy ",
    ))
    # text normalized, id deterministic over normalized text
    assert graph.created[0][3] == "Product strategy"
    assert item_id == skill_item_id("skill", "Product strategy")


def test_add_rejects_bad_kind_and_empty_text() -> None:
    with pytest.raises(SkillValidationError):
        asyncio.run(add_skill_item(goal_graph=_FakeGraph(), actor=_actor(), kind="widget", text="x"))
    with pytest.raises(SkillValidationError):
        asyncio.run(add_skill_item(goal_graph=_FakeGraph(), actor=_actor(), kind="skill", text="   "))


def test_confirm_edit_reject_delegate_and_carry_match() -> None:
    graph = _FakeGraph()
    from uuid import uuid4
    iid = uuid4()
    assert asyncio.run(confirm_skill_item(goal_graph=graph, actor=_actor(), item_id=iid)) is True
    assert graph.confirmed == [iid]
    assert asyncio.run(edit_skill_item(goal_graph=graph, actor=_actor(), item_id=iid, text=" new  text ")) is True
    assert graph.edited == [(iid, "new text")]  # normalized
    assert asyncio.run(reject_skill_item(goal_graph=graph, actor=_actor(), item_id=iid)) is True
    assert graph.rejected == [iid]


def test_edit_rejects_empty_text() -> None:
    with pytest.raises(SkillValidationError):
        asyncio.run(edit_skill_item(goal_graph=_FakeGraph(), actor=_actor(), item_id=__import__("uuid").uuid4(), text="  "))


def test_missing_item_returns_false() -> None:
    graph = _FakeGraph(); graph.match = False
    from uuid import uuid4
    iid = uuid4()
    assert asyncio.run(confirm_skill_item(goal_graph=graph, actor=_actor(), item_id=iid)) is False
    assert asyncio.run(reject_skill_item(goal_graph=graph, actor=_actor(), item_id=iid)) is False
