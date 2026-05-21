"""Unit tests for the ActorContext value object (D126, S44a)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from shared_kernel import ActorContext, TenantContext


def _tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id="11111111-1111-1111-1111-111111111111",
        jurisdiction="UK",
        cost_attribution_id="cost-1",
    )


def _actor_context(
    *,
    actor_id: str = "operator",
    role_list: frozenset[str] = frozenset({"operator"}),
    authorisation_set: frozenset[str] = frozenset({"portfolio.case.list"}),
) -> ActorContext:
    return ActorContext(
        tenant_context=_tenant_context(),
        actor_id=actor_id,
        role_list=role_list,
        authorisation_set=authorisation_set,
    )


def test_construction_happy_path() -> None:
    actor = _actor_context()
    assert actor.tenant_context == _tenant_context()
    assert actor.actor_id == "operator"
    assert actor.role_list == frozenset({"operator"})
    assert actor.authorisation_set == frozenset({"portfolio.case.list"})


def test_compose_shape_exposes_tenant_context() -> None:
    """ActorContext wraps TenantContext as a field — adapters extract it."""
    actor = _actor_context()
    assert isinstance(actor.tenant_context, TenantContext)
    assert actor.tenant_context.jurisdiction == "UK"


def test_missing_field_raises() -> None:
    with pytest.raises(TypeError):
        ActorContext(  # type: ignore[call-arg]
            tenant_context=_tenant_context(),
            actor_id="operator",
            role_list=frozenset({"operator"}),
        )


def test_empty_actor_id_rejected() -> None:
    with pytest.raises(ValueError, match="actor_id"):
        _actor_context(actor_id="")


def test_blank_actor_id_rejected() -> None:
    with pytest.raises(ValueError, match="actor_id"):
        _actor_context(actor_id="   ")


def test_empty_role_list_rejected() -> None:
    with pytest.raises(ValueError, match="role_list"):
        _actor_context(role_list=frozenset())


def test_empty_authorisation_set_is_valid() -> None:
    """An actor with no permissions is legitimate — every decorator
    check simply fails. Only role_list carries the non-empty invariant."""
    actor = _actor_context(authorisation_set=frozenset())
    assert actor.authorisation_set == frozenset()


def test_is_frozen() -> None:
    actor = _actor_context()
    with pytest.raises(FrozenInstanceError):
        actor.actor_id = "other"  # type: ignore[misc]


def test_value_equality() -> None:
    """Frozen dataclasses use value equality; frozensets compare by value."""
    a = _actor_context()
    b = _actor_context()
    assert a == b
    assert hash(a) == hash(b)


def test_inequality_on_authorisation_set() -> None:
    a = _actor_context(authorisation_set=frozenset({"portfolio.case.get"}))
    b = _actor_context(authorisation_set=frozenset({"portfolio.case.list"}))
    assert a != b


def test_role_list_is_a_frozenset() -> None:
    """The frozenset shape holds — ActorContext stays hashable."""
    actor = _actor_context(role_list=frozenset({"operator", "auditor"}))
    assert isinstance(actor.role_list, frozenset)
    assert hash(actor) == hash(_actor_context(
        role_list=frozenset({"auditor", "operator"})
    ))
