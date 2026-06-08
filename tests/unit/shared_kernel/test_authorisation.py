"""Unit tests for the authorisation decorator and policy (D126, S44a)."""

from __future__ import annotations

import asyncio

import pytest

from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_COMMITMENT_COMPLETE,
    DAILY_DRIVER_COMMITMENT_CREATE,
    DAILY_DRIVER_COMMITMENT_OBSERVE,
    DAILY_DRIVER_GOAL_RAISE_TARGET,
    DAILY_DRIVER_GOAL_READ,
    DAILY_DRIVER_ASSESSMENT_READ,
    DAILY_DRIVER_SUGGESTIONS_READ,
    DAILY_DRIVER_TODAY_READ,
    DAILY_DRIVER_TODAY_WRITE,
    DAILY_DRIVER_UNITS_CORRELATE,
    DAILY_DRIVER_UNITS_READ,
    INTAKE_RECORD_CREATE,
    INTAKE_RECORD_GET,
    INTAKE_RECORD_LIST,
    MESSAGING_MESSAGE_GET,
    MESSAGING_MESSAGE_LIST,
    MESSAGING_MESSAGE_RECEIVE,
    MESSAGING_MESSAGE_SEND,
    MESSAGING_PENDING_CLARIFICATION_CREATE,
    MESSAGING_PENDING_CLARIFICATION_EXPIRE,
    MESSAGING_PENDING_CLARIFICATION_RESOLVE,
    PORTFOLIO_CASE_CREATE,
    PORTFOLIO_CASE_GET,
    PORTFOLIO_CASE_LIST,
    PORTFOLIO_DATA_POINT_CREATE,
    PORTFOLIO_DATA_POINT_REVISE,
    ROLE_OPERATOR,
    AuthorisationDenied,
    authorisations_for_roles,
    requires_authorisation,
)

_TENANT_CONTEXT = TenantContext(
    tenant_id="11111111-1111-1111-1111-111111111111",
    jurisdiction="UK",
    cost_attribution_id="cost-1",
)


def _actor(*, authorisation_set: frozenset[str]) -> ActorContext:
    return ActorContext(
        tenant_context=_TENANT_CONTEXT,
        actor_id="operator",
        role_list=frozenset({ROLE_OPERATOR}),
        authorisation_set=authorisation_set,
    )


# --- authorisations_for_roles --------------------------------------


def test_operator_role_grants_the_phase_2a_permissions() -> None:
    """The operator role grants the five portfolio permissions, the
    three intake permissions (D127, S44b), the four messaging
    permissions (D129, S45), the three PendingClarification
    permissions (D134, S47), and the five daily-driver permissions
    (D157, S58; D162, S61) — twenty in total."""
    granted = authorisations_for_roles(frozenset({ROLE_OPERATOR}))
    assert granted == frozenset(
        {
            PORTFOLIO_CASE_CREATE,
            PORTFOLIO_CASE_LIST,
            PORTFOLIO_CASE_GET,
            PORTFOLIO_DATA_POINT_CREATE,
            PORTFOLIO_DATA_POINT_REVISE,
            INTAKE_RECORD_CREATE,
            INTAKE_RECORD_GET,
            INTAKE_RECORD_LIST,
            MESSAGING_MESSAGE_SEND,
            MESSAGING_MESSAGE_RECEIVE,
            MESSAGING_MESSAGE_GET,
            MESSAGING_MESSAGE_LIST,
            MESSAGING_PENDING_CLARIFICATION_CREATE,
            MESSAGING_PENDING_CLARIFICATION_RESOLVE,
            MESSAGING_PENDING_CLARIFICATION_EXPIRE,
            DAILY_DRIVER_TODAY_READ,
            DAILY_DRIVER_TODAY_WRITE,
            DAILY_DRIVER_COMMITMENT_CREATE,
            DAILY_DRIVER_COMMITMENT_COMPLETE,
            DAILY_DRIVER_COMMITMENT_OBSERVE,
            DAILY_DRIVER_GOAL_READ,
            DAILY_DRIVER_GOAL_RAISE_TARGET,
            DAILY_DRIVER_UNITS_READ,
            DAILY_DRIVER_UNITS_CORRELATE,
            DAILY_DRIVER_ASSESSMENT_READ,
            DAILY_DRIVER_SUGGESTIONS_READ,
        }
    )


def test_unknown_role_grants_nothing() -> None:
    assert authorisations_for_roles(frozenset({"stranger"})) == frozenset()


def test_role_union_resolves_across_multiple_roles() -> None:
    granted = authorisations_for_roles(frozenset({ROLE_OPERATOR, "stranger"}))
    assert PORTFOLIO_CASE_CREATE in granted


def test_empty_role_set_grants_nothing() -> None:
    assert authorisations_for_roles(frozenset()) == frozenset()


# --- requires_authorisation: happy path ----------------------------


def test_happy_path_executes_the_wrapped_function() -> None:
    @requires_authorisation(PORTFOLIO_CASE_CREATE)
    async def use_case(*, actor: ActorContext, title: str) -> str:
        return f"created:{title}"

    actor = _actor(authorisation_set=frozenset({PORTFOLIO_CASE_CREATE}))
    result = asyncio.run(use_case(actor=actor, title="alpha"))
    assert result == "created:alpha"


def test_happy_path_with_a_broad_authorisation_set() -> None:
    @requires_authorisation(PORTFOLIO_CASE_LIST)
    async def use_case(*, actor: ActorContext) -> str:
        return "listed"

    actor = _actor(
        authorisation_set=authorisations_for_roles(
            frozenset({ROLE_OPERATOR})
        )
    )
    assert asyncio.run(use_case(actor=actor)) == "listed"


# --- requires_authorisation: deny path -----------------------------


def test_deny_path_raises_authorisation_denied() -> None:
    @requires_authorisation(PORTFOLIO_DATA_POINT_REVISE)
    async def use_case(*, actor: ActorContext) -> str:
        return "revised"

    actor = _actor(authorisation_set=frozenset({PORTFOLIO_CASE_LIST}))
    with pytest.raises(AuthorisationDenied) as excinfo:
        asyncio.run(use_case(actor=actor))
    assert excinfo.value.permission == PORTFOLIO_DATA_POINT_REVISE
    assert excinfo.value.actor_id == "operator"


def test_deny_path_does_not_call_through() -> None:
    calls: list[str] = []

    @requires_authorisation(PORTFOLIO_CASE_GET)
    async def use_case(*, actor: ActorContext) -> None:
        calls.append("ran")

    actor = _actor(authorisation_set=frozenset())
    with pytest.raises(AuthorisationDenied):
        asyncio.run(use_case(actor=actor))
    assert calls == []


def test_empty_authorisation_set_denies_everything() -> None:
    @requires_authorisation(PORTFOLIO_CASE_CREATE)
    async def use_case(*, actor: ActorContext) -> str:
        return "created"

    actor = _actor(authorisation_set=frozenset())
    with pytest.raises(AuthorisationDenied):
        asyncio.run(use_case(actor=actor))


# --- requires_authorisation: misuse --------------------------------


def test_missing_actor_kwarg_raises_type_error() -> None:
    @requires_authorisation(PORTFOLIO_CASE_LIST)
    async def use_case(*, title: str) -> str:
        return title

    with pytest.raises(TypeError, match="actor: ActorContext"):
        asyncio.run(use_case(title="alpha"))


def test_actor_of_wrong_type_raises_type_error() -> None:
    @requires_authorisation(PORTFOLIO_CASE_LIST)
    async def use_case(*, actor: object) -> str:
        return "ran"

    with pytest.raises(TypeError, match="actor: ActorContext"):
        asyncio.run(use_case(actor="not-an-actor-context"))


# --- requires_authorisation: signature preservation ----------------


def test_decorator_preserves_name_and_docstring() -> None:
    @requires_authorisation(PORTFOLIO_CASE_LIST)
    async def list_cases_use_case(*, actor: ActorContext) -> None:
        """The original docstring."""

    assert list_cases_use_case.__name__ == "list_cases_use_case"
    assert list_cases_use_case.__doc__ == "The original docstring."


def test_decorator_preserves_signature_via_wrapped() -> None:
    import inspect

    @requires_authorisation(PORTFOLIO_CASE_LIST)
    async def use_case(*, actor: ActorContext, page_size: int) -> None:
        """Docstring."""

    params = inspect.signature(use_case).parameters
    assert "actor" in params
    assert "page_size" in params


# --- AuthorisationDenied exception ---------------------------------


def test_authorisation_denied_attributes_and_message() -> None:
    exc = AuthorisationDenied(
        permission=PORTFOLIO_CASE_CREATE, actor_id="actor-7"
    )
    assert exc.permission == PORTFOLIO_CASE_CREATE
    assert exc.actor_id == "actor-7"
    assert PORTFOLIO_CASE_CREATE in str(exc)
    assert "actor-7" in str(exc)
