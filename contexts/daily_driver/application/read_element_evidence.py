"""read_element_evidence — the read-only element-evidence summary (D202, S103b).

Surfaces where matched signal landed: per authored element, how many units
evidence it, plus the unbound-bucket size (units that matched no element — the
emergent loop's queue, S104). Read-only; the relink/unlink correction paths are
S103c. Behind ``CDD_READ`` (the user inspecting their own model's evidence).
"""

from __future__ import annotations

from contexts.daily_driver.domain.goal_assessment import (
    ElementEvidenceSummary,
    summarise_element_evidence,
)
from contexts.daily_driver.ports.unit_graph import UnitGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_READ,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_CDD_READ)
async def read_element_evidence(
    *, unit_graph: UnitGraphPort, actor: ActorContext
) -> ElementEvidenceSummary:
    """Return per-element unit counts + the unbound-bucket size (S103b)."""
    evidence = await unit_graph.list_element_evidence(
        tenant_context=actor.tenant_context
    )
    units = await unit_graph.list_units(tenant_context=actor.tenant_context)
    return summarise_element_evidence(evidence, total_units=len(units))


__all__ = ["read_element_evidence"]
