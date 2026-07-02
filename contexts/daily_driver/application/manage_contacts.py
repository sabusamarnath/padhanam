"""Contact proof + management use cases (S103u, D222).

The operator proofs the email-seeded contacts (confirm → user_authored, enrich with
degree/strength/reachability, or reject) and adds contacts email did not surface
(the manual capture route — a LinkedIn-known or hand-added person). The reads back
the derive + the inline lead surface. Reuses the D215/S103o extract-and-proof shape
and the S103a proof-affordance pattern; the operator is ground truth on the
relationship (D200).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from contexts.daily_driver.domain.contacts import (
    CAPTURE_SOURCES,
    DEGREES,
    REACHABILITIES,
    STRENGTHS,
    ContactView,
)
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_READ,
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)


class ContactValidationError(ValueError):
    """A contact field is outside its allowed vocabulary, or the name is empty."""


def _check_enrichment(
    *, degree: str | None, strength: str | None, reachability: str | None
) -> None:
    if degree is not None and degree not in DEGREES:
        raise ContactValidationError(f"degree must be one of {list(DEGREES)}")
    if strength is not None and strength not in STRENGTHS:
        raise ContactValidationError(f"strength must be one of {list(STRENGTHS)}")
    if reachability is not None and reachability not in REACHABILITIES:
        raise ContactValidationError(
            f"reachability must be one of {list(REACHABILITIES)}"
        )


@requires_authorisation(DAILY_DRIVER_CDD_READ)
async def list_contacts(
    *, goal_graph: GoalGraphPort, actor: ActorContext
) -> tuple[ContactView, ...]:
    """The tenant's contacts (D222) for the proof surface + a lead's inline list."""
    return await goal_graph.list_contacts(tenant_context=actor.tenant_context)


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def add_contact(
    *,
    goal_graph: GoalGraphPort,
    actor: ActorContext,
    name: str,
    company: str,
    degree: str | None = None,
    strength: str | None = None,
    reachability: str | None = None,
    capture_source: str = "manual",
) -> UUID:
    """Add a user-authored contact email did not surface (D222) — the manual capture
    route (hand-added, or a LinkedIn-known person tagged ``linkedin``). Returns the
    new contact's id. Validates the vocabularies."""
    name = name.strip()
    if not name:
        raise ContactValidationError("name is required")
    if capture_source not in CAPTURE_SOURCES:
        raise ContactValidationError(
            f"capture_source must be one of {list(CAPTURE_SOURCES)}"
        )
    _check_enrichment(degree=degree, strength=strength, reachability=reachability)
    contact_id = uuid4()
    await goal_graph.create_contact(
        tenant_context=actor.tenant_context, contact_id=contact_id, name=name,
        company=(company.strip() or None), degree=degree, strength=strength,
        reachability=reachability, capture_source=capture_source,
    )
    return contact_id


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def confirm_contact(
    *, goal_graph: GoalGraphPort, actor: ActorContext, contact_id: UUID
) -> bool:
    """Confirm a system-suggested contact → user_authored (D222)."""
    return await goal_graph.confirm_contact(
        tenant_context=actor.tenant_context, contact_id=contact_id
    )


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def enrich_contact(
    *,
    goal_graph: GoalGraphPort,
    actor: ActorContext,
    contact_id: UUID,
    degree: str | None,
    strength: str | None,
    reachability: str | None,
) -> bool:
    """Enrich a contact with degree/strength/reachability (D222) — the operator
    authors the relationship, flipping it to user_authored."""
    _check_enrichment(degree=degree, strength=strength, reachability=reachability)
    return await goal_graph.enrich_contact(
        tenant_context=actor.tenant_context, contact_id=contact_id, degree=degree,
        strength=strength, reachability=reachability,
    )


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def reject_contact(
    *, goal_graph: GoalGraphPort, actor: ActorContext, contact_id: UUID
) -> bool:
    """Reject (delete) a contact (D222)."""
    return await goal_graph.reject_contact(
        tenant_context=actor.tenant_context, contact_id=contact_id
    )


__all__ = [
    "ContactValidationError", "add_contact", "confirm_contact", "enrich_contact",
    "list_contacts", "reject_contact",
]
