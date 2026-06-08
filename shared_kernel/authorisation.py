"""Authorisation decorator and Phase 2-A policy (D126, S44a).

D126 sub-commitment 2: ``requires_authorisation`` is the decorator
applied at the use-case boundary. It wraps a use-case async function
whose keyword arguments include ``actor: ActorContext``, checks a
required permission string against ``actor.authorisation_set``, and
raises ``AuthorisationDenied`` when the check fails. The HTTP layer
translates ``AuthorisationDenied`` to a 403 response with the
``ErrorResponse`` shape per D98, registered with the
auth-cross-cutting handlers at ``apps/api/_auth_errors.py`` per D104.

Enforcing authorisation at one decorated boundary — rather than
inline in each use-case body — keeps the authorisation surface
grep-able: a procurement auditor can verify completeness of
enforcement by reading the decorator applications, per Decision 7's
trivial-check-at-one-boundary commitment.

This module also carries the Phase 2-A authorisation *policy*: the
five portfolio permission strings as named constants, and the
hardcoded role-to-authorisation lookup. The policy lives here, in
shared_kernel, rather than at the auth middleware because the CLI
synthesises ActorContext without passing through HTTP middleware —
a middleware-local lookup would force the permission set into two
places and risk drift. The HTTP ``get_actor_context`` dependency and
the CLI both call ``authorisations_for_roles``. The richer
per-tenant / registry-backed lookup activates at the role-hierarchy
deferred-decisions trigger.

Framework-free per D16 — shared_kernel is policed; stdlib plus the
sibling ActorContext only.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from shared_kernel.actor_context import ActorContext

# --- Phase 2-A portfolio permissions -------------------------------
# Named once here so the decorator applications in the portfolio use
# cases and the role-to-authorisation lookup below reference one
# source — the parallel-drafting fragility of bare string literals
# across surfaces is removed by the single definition.
PORTFOLIO_CASE_CREATE = "portfolio.case.create"
PORTFOLIO_CASE_LIST = "portfolio.case.list"
PORTFOLIO_CASE_GET = "portfolio.case.get"
PORTFOLIO_DATA_POINT_CREATE = "portfolio.data_point.create"
PORTFOLIO_DATA_POINT_REVISE = "portfolio.data_point.revise"

# --- Phase 2-A intake permissions (D127, S44b) ---------------------
INTAKE_RECORD_CREATE = "intake.record.create"
INTAKE_RECORD_GET = "intake.record.get"
INTAKE_RECORD_LIST = "intake.record.list"

# --- Phase 2-A messaging permissions (D129, S45) -------------------
MESSAGING_MESSAGE_SEND = "messaging.message.send"
MESSAGING_MESSAGE_RECEIVE = "messaging.message.receive"
MESSAGING_MESSAGE_GET = "messaging.message.get"
MESSAGING_MESSAGE_LIST = "messaging.message.list"

# --- Phase 2-A PendingClarification permissions (D134, S47) -------
MESSAGING_PENDING_CLARIFICATION_CREATE = (
    "messaging.pending_clarification.create"
)
MESSAGING_PENDING_CLARIFICATION_RESOLVE = (
    "messaging.pending_clarification.resolve"
)
MESSAGING_PENDING_CLARIFICATION_EXPIRE = (
    "messaging.pending_clarification.expire"
)

# --- Phase 2-A daily-driver permissions (D157, S58; D162, S61) -----
DAILY_DRIVER_TODAY_READ = "daily_driver.today.read"
DAILY_DRIVER_TODAY_WRITE = "daily_driver.today.write"
DAILY_DRIVER_COMMITMENT_CREATE = "daily_driver.commitment.create"
DAILY_DRIVER_COMMITMENT_COMPLETE = "daily_driver.commitment.complete"
DAILY_DRIVER_COMMITMENT_OBSERVE = "daily_driver.commitment.observe"
# --- Phase 2-A goal-layer permissions (D163, S62) ------------------
DAILY_DRIVER_GOAL_READ = "daily_driver.goal.read"
DAILY_DRIVER_GOAL_RAISE_TARGET = "daily_driver.goal.raise_target"
# --- Phase 2-A work-unit correlation permissions (D168, S66) --------
DAILY_DRIVER_UNITS_READ = "daily_driver.units.read"
DAILY_DRIVER_UNITS_CORRELATE = "daily_driver.units.correlate"

# --- Phase 2-A role-to-authorisation policy ------------------------
ROLE_OPERATOR = "operator"

_ROLE_AUTHORISATIONS: dict[str, frozenset[str]] = {
    ROLE_OPERATOR: frozenset(
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
        }
    ),
}


def authorisations_for_roles(roles: frozenset[str]) -> frozenset[str]:
    """Resolve the union of authorisations granted to a set of roles.

    Phase 2-A has the single role ``operator``; the union shape
    supports the role-hierarchy deferred-decisions entry as a pure
    extension at activation. Unknown roles contribute nothing.
    """
    granted: set[str] = set()
    for role in roles:
        granted |= _ROLE_AUTHORISATIONS.get(role, frozenset())
    return frozenset(granted)


class AuthorisationDenied(Exception):
    """Raised by ``requires_authorisation`` when the actor lacks a permission.

    Carries the required permission and the actor_id from the failed
    check so the HTTP handler can surface a typed 403 and fire an
    ``AUTHZ_DENIAL`` security event. The HTTP message names the
    required permission only — never the actor's full authorisation
    set.
    """

    def __init__(self, *, permission: str, actor_id: str) -> None:
        super().__init__(
            f"actor {actor_id!r} lacks the required authorisation "
            f"{permission!r}"
        )
        self.permission = permission
        self.actor_id = actor_id


_R = TypeVar("_R")


def requires_authorisation(
    permission: str,
) -> Callable[[Callable[..., Awaitable[_R]]], Callable[..., Awaitable[_R]]]:
    """Decorate a use-case async function with a use-case-boundary check.

    The decorated function must receive an ``actor: ActorContext``
    keyword argument (every portfolio use case uses keyword-only
    parameters). The decorator reads ``permission`` at decoration
    time, finds the ActorContext at invocation time, and checks
    ``permission in actor.authorisation_set``; it raises
    ``AuthorisationDenied`` when the check fails and otherwise calls
    through. ``functools.wraps`` preserves the wrapped function's
    name, docstring, and signature.
    """

    def decorator(
        fn: Callable[..., Awaitable[_R]],
    ) -> Callable[..., Awaitable[_R]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> _R:
            actor = kwargs.get("actor")
            if not isinstance(actor, ActorContext):
                raise TypeError(
                    f"@requires_authorisation({permission!r}) wraps "
                    f"{fn.__name__}, which must receive an "
                    "'actor: ActorContext' keyword argument"
                )
            if permission not in actor.authorisation_set:
                raise AuthorisationDenied(
                    permission=permission, actor_id=actor.actor_id
                )
            return await fn(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "DAILY_DRIVER_COMMITMENT_COMPLETE",
    "DAILY_DRIVER_COMMITMENT_CREATE",
    "DAILY_DRIVER_COMMITMENT_OBSERVE",
    "DAILY_DRIVER_GOAL_RAISE_TARGET",
    "DAILY_DRIVER_GOAL_READ",
    "DAILY_DRIVER_TODAY_READ",
    "DAILY_DRIVER_TODAY_WRITE",
    "DAILY_DRIVER_UNITS_CORRELATE",
    "DAILY_DRIVER_UNITS_READ",
    "INTAKE_RECORD_CREATE",
    "INTAKE_RECORD_GET",
    "INTAKE_RECORD_LIST",
    "MESSAGING_MESSAGE_GET",
    "MESSAGING_MESSAGE_LIST",
    "MESSAGING_MESSAGE_RECEIVE",
    "MESSAGING_MESSAGE_SEND",
    "MESSAGING_PENDING_CLARIFICATION_CREATE",
    "MESSAGING_PENDING_CLARIFICATION_EXPIRE",
    "MESSAGING_PENDING_CLARIFICATION_RESOLVE",
    "PORTFOLIO_CASE_CREATE",
    "PORTFOLIO_CASE_GET",
    "PORTFOLIO_CASE_LIST",
    "PORTFOLIO_DATA_POINT_CREATE",
    "PORTFOLIO_DATA_POINT_REVISE",
    "ROLE_OPERATOR",
    "AuthorisationDenied",
    "authorisations_for_roles",
    "requires_authorisation",
]
