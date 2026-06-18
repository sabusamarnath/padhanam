"""Proof read + accept/reject/correct write paths for the authored CDD (S102, D200).

The authoring-time proof actions: read a goal's drafted CDD for review, accept an
element (``proof_state = accepted``), reject it (a user-initiated delete — allowed
under the no-auto-deletion invariant), or lightly correct its label (flipping
``provenance_origin`` to ``user_authored``, the D200 ground-truth signal). These
are one-shot proof actions; the ongoing relink/unlink/edit loop and
correction-as-learning-signal are S103.
"""

from __future__ import annotations

from uuid import UUID

from contexts.daily_driver.domain.cdd import (
    ElementKind,
    GoalCddView,
    ProofState,
    ProvenanceOrigin,
)
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_READ,
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_CDD_READ)
async def read_goal_cdd(
    *, goal_graph: GoalGraphPort, actor: ActorContext, outcome_id: UUID
) -> GoalCddView:
    """Read a goal's authored CDD for proof review (S102, D200)."""
    return await goal_graph.read_goal_cdd(
        tenant_context=actor.tenant_context, outcome_id=outcome_id
    )


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def accept_cdd_element(
    *,
    goal_graph: GoalGraphPort,
    actor: ActorContext,
    kind: ElementKind,
    element_id: UUID,
) -> bool:
    """Mark an authored element accepted (S102)."""
    return await goal_graph.accept_authored_element(
        tenant_context=actor.tenant_context, kind=kind, element_id=element_id
    )


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def correct_cdd_element(
    *,
    goal_graph: GoalGraphPort,
    actor: ActorContext,
    kind: ElementKind,
    element_id: UUID,
    label: str,
) -> bool:
    """Edit an authored element's label, flipping its origin to user_authored
    (S102, D200 — the ground-truth correction signal)."""
    return await goal_graph.correct_authored_element(
        tenant_context=actor.tenant_context,
        kind=kind,
        element_id=element_id,
        label=label,
    )


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def reject_cdd_element(
    *,
    goal_graph: GoalGraphPort,
    actor: ActorContext,
    kind: ElementKind,
    element_id: UUID,
) -> bool:
    """Remove an authored element — the user-initiated delete (S102)."""
    return await goal_graph.reject_authored_element(
        tenant_context=actor.tenant_context, kind=kind, element_id=element_id
    )


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def accept_cdd_outcome(
    *, goal_graph: GoalGraphPort, actor: ActorContext, outcome_id: UUID
) -> bool:
    """Accept the authored outcome stance (proof accept on the terminal
    element, S103a)."""
    return await goal_graph.accept_authored_outcome(
        tenant_context=actor.tenant_context, outcome_id=outcome_id
    )


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def correct_cdd_outcome(
    *, goal_graph: GoalGraphPort, actor: ActorContext, outcome_id: UUID, label: str
) -> bool:
    """Edit the authored outcome text, flipping its origin to user_authored and
    its proof state to accepted (the correction is its own proof, S103a/D200)."""
    await goal_graph.set_authored_outcome(
        tenant_context=actor.tenant_context,
        outcome_id=outcome_id,
        expected_outcome=label,
        origin=ProvenanceOrigin.USER_AUTHORED,
        proof_state=ProofState.ACCEPTED,
    )
    return True


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def reject_cdd_outcome(
    *, goal_graph: GoalGraphPort, actor: ActorContext, outcome_id: UUID
) -> bool:
    """Clear the authored outcome stance — the user-initiated reject (S103a)."""
    return await goal_graph.reject_authored_outcome(
        tenant_context=actor.tenant_context, outcome_id=outcome_id
    )


__all__ = [
    "accept_cdd_element",
    "accept_cdd_outcome",
    "correct_cdd_element",
    "correct_cdd_outcome",
    "read_goal_cdd",
    "reject_cdd_element",
    "reject_cdd_outcome",
]
