"""Correct a unit's element evidence — relink, unlink (D203, S103c).

The user's corrections over the matcher's bindings: relink retargets a unit's
``EVIDENCES`` edge to a different authored element, unlink removes it. Both make
the unit **user-owned** (the re-runnable re-match never overwrites it — correction
precedence, D203) and mark the new edge user-corrected. Behind ``CDD_WRITE`` (the
user correcting their own model), tenant-scoped. The append-only correction
capture (the learning signal) layers on at the audit-emit seam (S103c commit 2);
consuming the signal is a later session.
"""

from __future__ import annotations

from uuid import UUID

from contexts.daily_driver.domain.cdd import ElementKind
from contexts.daily_driver.ports.unit_graph import UnitGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def unlink_cdd_evidence(
    *,
    unit_graph: UnitGraphPort,
    actor: ActorContext,
    unit_id: UUID,
    kind: ElementKind,
    element_id: UUID,
) -> bool:
    """Remove one of a unit's element bindings; mark the unit user-owned (D203).
    Returns ``False`` when the binding is absent or cross-tenant."""
    return await unit_graph.unlink_element_evidence(
        tenant_context=actor.tenant_context,
        unit_id=unit_id,
        element_kind=kind,
        element_id=element_id,
    )


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def relink_cdd_evidence(
    *,
    unit_graph: UnitGraphPort,
    actor: ActorContext,
    unit_id: UUID,
    from_kind: ElementKind,
    from_element_id: UUID,
    to_kind: ElementKind,
    to_element_id: UUID,
) -> bool:
    """Retarget one of a unit's element bindings to a different element; mark it
    user-corrected and the unit user-owned (D203). Touches the one named binding,
    not all of a multi-attach unit's bindings. Returns ``False`` when the
    from-binding or the to-element is absent."""
    return await unit_graph.relink_element_evidence(
        tenant_context=actor.tenant_context,
        unit_id=unit_id,
        from_kind=from_kind,
        from_element_id=from_element_id,
        to_kind=to_kind,
        to_element_id=to_element_id,
    )


__all__ = ["relink_cdd_evidence", "unlink_cdd_evidence"]
