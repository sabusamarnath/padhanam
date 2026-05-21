"""ActorContext — request-scoped actor identity and authorisation envelope (D126, S44a).

D126 introduces ActorContext as the request-scoped value object that
flows into every portfolio use case from S44a onward: it composes the
existing TenantContext as a field and adds the acting actor's identity
plus the authorisation surface the use-case-boundary decorator checks.

Compose shape, not subsume: ActorContext *wraps* TenantContext rather
than replacing it. Adapters continue to consume TenantContext via
``actor.tenant_context`` extraction, so adapter signatures are
unchanged; single-concern value objects are preserved per the
hexagonal posture.

ActorContext is distinct from ActorReference. ActorReference (at
``shared_kernel/actor_reference.py``) is the minimal *persisted*
authoring-identity value object stamped onto DataPoint and Assertion
records; ActorContext is the *request-scoped* envelope carrying
capability. D126 supersedes D124's forward commitment that
``authored_by`` would become ActorContext: a persisted record cannot
honestly carry a request-time authorisation snapshot. A use case
receives ActorContext and derives ``ActorReference(user_id=actor.actor_id)``
when stamping authorship.

Framework-free per D16 — shared_kernel is policed; stdlib plus the
sibling TenantContext only. Pydantic is forbidden here by the
``shared-kernel-policed`` import-linter contract, so the
frozen-dataclass shape is structurally pre-empted, consistent with
TenantContext.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_kernel.tenant_context import TenantContext


@dataclass(frozen=True)
class ActorContext:
    """The request-scoped actor identity and authorisation envelope (D126).

    Composes TenantContext plus the acting actor's id, role list, and
    authorisation set. Frozen — referentially equal by value, which is
    why it lives in shared_kernel alongside TenantContext.
    """

    tenant_context: TenantContext
    actor_id: str
    role_list: frozenset[str]
    authorisation_set: frozenset[str]

    def __post_init__(self) -> None:
        if self.tenant_context is None:  # type: ignore[redundant-expr]
            raise ValueError("ActorContext.tenant_context must not be None")
        if not self.actor_id or not self.actor_id.strip():
            raise ValueError("ActorContext.actor_id must be non-empty")
        if not self.role_list:
            raise ValueError("ActorContext.role_list must be non-empty")
        if self.authorisation_set is None:  # type: ignore[redundant-expr]
            raise ValueError(
                "ActorContext.authorisation_set must not be None"
            )


__all__ = ["ActorContext"]
