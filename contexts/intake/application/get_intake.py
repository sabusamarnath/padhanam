"""get_intake read use case (D127).

A thin read use case over the IntakeRepository's single-record
surface. Returns ``None`` when the intake does not exist for the
tenant.

S44b: accepts an ActorContext, applies the ``requires_authorisation``
decorator, and extracts ``actor.tenant_context`` for the adapter call.
"""

from __future__ import annotations

from uuid import UUID

from contexts.intake.domain import IntakeRecord
from contexts.intake.ports.intake_repository import IntakeRepository
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    INTAKE_RECORD_GET,
    requires_authorisation,
)


@requires_authorisation(INTAKE_RECORD_GET)
async def get_intake(
    *,
    repository: IntakeRepository,
    actor: ActorContext,
    intake_id: UUID,
) -> IntakeRecord | None:
    """Return the IntakeRecord, or None when absent for the tenant."""
    return await repository.get_by_id(
        tenant_context=actor.tenant_context, intake_id=intake_id
    )


__all__ = ["get_intake"]
