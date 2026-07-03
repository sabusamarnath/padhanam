"""Skills-profile proof + management use cases (S103af, D238).

The operator proofs the CV-seeded skill items (confirm → confirmed, edit the text, or
reject) and adds items the CV did not surface (the manual route). Reuses the D215/
D222 extract-and-proof shape; the operator is ground truth on the profile (D200). The
seed itself is ``extract_cv_profile`` (leg two); these are the proof affordances.
"""

from __future__ import annotations

from uuid import UUID

from contexts.daily_driver.domain.cv_extraction import skill_item_id
from contexts.daily_driver.domain.skills import KINDS, SkillItemView
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_READ,
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)


class SkillValidationError(ValueError):
    """A skill item's kind is outside the vocabulary, or its text is empty."""


@requires_authorisation(DAILY_DRIVER_CDD_READ)
async def list_skill_items(
    *, goal_graph: GoalGraphPort, actor: ActorContext
) -> tuple[SkillItemView, ...]:
    """The tenant's skill-profile items (D238) for the proof surface."""
    return await goal_graph.list_skill_items(tenant_context=actor.tenant_context)


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def add_skill_item(
    *, goal_graph: GoalGraphPort, actor: ActorContext, kind: str, text: str,
) -> UUID:
    """Add a user-authored skill item the CV did not surface (D238). Confirmed from
    the start (the operator authored it). Returns the new item's id. On a manual add
    matching an existing extracted item's deterministic id, MERGEs onto it rather than
    duplicating."""
    kind = (kind or "").strip()
    text = " ".join((text or "").split())
    if kind not in KINDS:
        raise SkillValidationError(f"kind must be one of {list(KINDS)}")
    if not text:
        raise SkillValidationError("text is required")
    # Reuse the deterministic id so a manual add of an item that would also extract
    # collapses onto one node (idempotent) rather than creating a duplicate.
    item_id = skill_item_id(kind, text)
    await goal_graph.create_skill_item(
        tenant_context=actor.tenant_context, item_id=item_id, kind=kind, text=text,
    )
    return item_id


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def confirm_skill_item(
    *, goal_graph: GoalGraphPort, actor: ActorContext, item_id: UUID
) -> bool:
    """Confirm a suggested item → confirmed (D238)."""
    return await goal_graph.confirm_skill_item(
        tenant_context=actor.tenant_context, item_id=item_id
    )


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def edit_skill_item(
    *, goal_graph: GoalGraphPort, actor: ActorContext, item_id: UUID, text: str
) -> bool:
    """Edit a skill item's text → confirmed (an authoring act, D238)."""
    text = " ".join((text or "").split())
    if not text:
        raise SkillValidationError("text is required")
    return await goal_graph.edit_skill_item(
        tenant_context=actor.tenant_context, item_id=item_id, text=text
    )


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def reject_skill_item(
    *, goal_graph: GoalGraphPort, actor: ActorContext, item_id: UUID
) -> bool:
    """Reject (delete) a skill item (D238)."""
    return await goal_graph.reject_skill_item(
        tenant_context=actor.tenant_context, item_id=item_id
    )


__all__ = [
    "SkillValidationError", "add_skill_item", "confirm_skill_item",
    "edit_skill_item", "list_skill_items", "reject_skill_item",
]
