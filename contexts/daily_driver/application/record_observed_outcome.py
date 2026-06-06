"""record_observed_outcome use case (D162).

Captures the observed outcome of a Commitment after the fact — the back
half of the minimal expected-versus-observed loop. Sets the free-text
observation, the coarse ``outcome_status``, and the ``observed_at``
timestamp (the new progress signal that, with the completion log, feeds
the derived ``last_progress_at`` used by the drop-candidate query).
Setting ``outcome_status`` to ``DROPPED`` is how the operator acts on a
drop-candidate recommendation — a user-initiated status change, never an
auto-delete (D162, the no-auto-deletion invariant). Returns ``None`` when
the Commitment does not exist on the actor's tenant.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from contexts.daily_driver.domain.commitment import Commitment, OutcomeStatus
from contexts.daily_driver.ports.commitment_repository import (
    CommitmentRepository,
)
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_COMMITMENT_OBSERVE,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_COMMITMENT_OBSERVE)
async def record_observed_outcome(
    *,
    repository: CommitmentRepository,
    actor: ActorContext,
    commitment_id: UUID,
    observed_outcome: str | None,
    outcome_status: OutcomeStatus,
) -> Commitment | None:
    """Record what transpired for a Commitment; None when it is absent."""
    return await repository.record_observed_outcome(
        tenant_context=actor.tenant_context,
        commitment_id=commitment_id,
        observed_outcome=observed_outcome,
        outcome_status=outcome_status,
        observed_at=datetime.now(timezone.utc),
    )


__all__ = ["record_observed_outcome"]
