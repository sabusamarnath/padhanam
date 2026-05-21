"""ActorReference — placeholder actor-identity value object (D124, S43).

A minimal reference to the actor that authored a portfolio
``DataPoint`` or ``Assertion``. ActorReference commits only the
field the Revisable Protocol's ``actor`` parameter and the
``authored_by`` field require at S43; it is superseded at S44 by
the full ActorContext per D116, which extends the existing
TenantContext shape with actor identity, role list, and
authorisation set. The S44 supersession extends shape and home
without renaming.

Resisting an ``actor_type`` discriminator now is deliberate: the
machine-actor variant has a named activation trigger in
``charter/deferred-decisions.md`` (principal polymorphic shape);
adding the field pre-emptively is the forward-compat
substrate-depth overreach the methodology stream is surfacing.

Framework-free per D16 — shared_kernel is policed; stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActorReference:
    """A minimal reference to an authoring actor (D124 placeholder)."""

    user_id: str

    def __post_init__(self) -> None:
        if not self.user_id:
            raise ValueError("ActorReference.user_id must be non-empty")
