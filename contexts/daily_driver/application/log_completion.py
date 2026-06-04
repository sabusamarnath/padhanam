"""log_commitment_completion use case (D157).

Appends one entry to a Commitment's completion log — the action that
clears an overdue ("behind on this") item at render. Returns ``None``
when the Commitment does not exist on the actor's tenant.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.daily_driver.domain.commitment import CommitmentCompletion
from contexts.daily_driver.ports.commitment_repository import (
    CommitmentRepository,
)
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_COMMITMENT_COMPLETE,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_COMMITMENT_COMPLETE)
async def log_commitment_completion(
    *,
    repository: CommitmentRepository,
    actor: ActorContext,
    commitment_id: UUID,
) -> CommitmentCompletion | None:
    """Append a completion for the Commitment; None when it is absent."""
    tenant_context = actor.tenant_context
    commitment = await repository.get_commitment(
        tenant_context=tenant_context, commitment_id=commitment_id
    )
    if commitment is None:
        return None
    completion = CommitmentCompletion(
        id=uuid4(),
        commitment_id=commitment_id,
        tenant_id=UUID(tenant_context.tenant_id),
        jurisdiction=tenant_context.jurisdiction,
        completed_at=datetime.now(timezone.utc),
    )
    await repository.add_completion(
        tenant_context=tenant_context, completion=completion
    )
    return completion


__all__ = ["log_commitment_completion"]
