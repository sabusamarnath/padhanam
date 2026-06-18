"""Author the CDD — add a user-authored element, reclassify across types (S103a).

These are the authoring-completion write paths over the S102 proof layer (D200):
the user adds an element the draft missed (the path by which externals enter the
model at all, given the zero-externals draft), and reclassifies an element the
draft mis-typed (D201). Both are user-authored corrections, so they persist with
``provenance_origin = user_authored``; an added element is also ``accepted`` (the
act of authoring is its proof). The matcher's SERVES/LEVER_FOR layer is untouched.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from contexts.daily_driver.domain.cdd import (
    ElementKind,
    ProofState,
    ProvenanceOrigin,
    required_edge_type,
)
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def add_cdd_element(
    *,
    goal_graph: GoalGraphPort,
    actor: ActorContext,
    outcome_id: UUID,
    kind: ElementKind,
    label: str,
) -> UUID:
    """Add a user-authored lever / intermediary / external to a goal's CDD (S103a).

    The element persists ``user_authored`` / ``accepted`` (authoring is its own
    proof) and is wired with a default edge to the outcome so it joins the causal
    chain (lever/intermediary ``FEEDS``, external ``INFLUENCES`` — the drafter's
    fallback shape). The outcome is authored through the outcome proof path, not
    here, since it is the goal's single terminal node (D199), not an element node.
    """
    element_id = uuid4()
    await goal_graph.write_authored_element(
        tenant_context=actor.tenant_context,
        outcome_id=outcome_id,
        kind=kind,
        element_id=element_id,
        label=label,
        origin=ProvenanceOrigin.USER_AUTHORED,
        proof_state=ProofState.ACCEPTED,
    )
    await goal_graph.write_authored_edge(
        tenant_context=actor.tenant_context,
        edge_type=required_edge_type(kind),
        source_kind=kind.value,
        source_id=element_id,
        target_kind="outcome",
        target_id=outcome_id,
    )
    return element_id


__all__ = ["add_cdd_element"]
