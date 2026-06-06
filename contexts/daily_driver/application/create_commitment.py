"""create_commitment use case (D157).

Mints a user-authored ``Commitment`` and persists it. The id and
``created_at`` are minted in the application layer (the portfolio
write-path precedent), keeping the domain pure and deterministic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.daily_driver.domain.commitment import Commitment
from contexts.daily_driver.ports.commitment_repository import (
    CommitmentRepository,
)
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_COMMITMENT_CREATE,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_COMMITMENT_CREATE)
async def create_commitment(
    *,
    repository: CommitmentRepository,
    actor: ActorContext,
    name: str,
    expected_interval_days: int,
    expected_outcome: str | None = None,
) -> Commitment:
    """Create and persist a Commitment for the actor's tenant.

    ``expected_outcome`` is the free-text expectation captured forward at
    creation (D162) — the front half of the expected-versus-observed loop.
    Optional so the S58 create-flow stays valid; the surface captures it.
    """
    tenant_context = actor.tenant_context
    commitment = Commitment(
        id=uuid4(),
        tenant_id=UUID(tenant_context.tenant_id),
        jurisdiction=tenant_context.jurisdiction,
        name=name,
        expected_interval_days=expected_interval_days,
        authored_by_user_id=actor.actor_id,
        created_at=datetime.now(timezone.utc),
        expected_outcome=expected_outcome,
    )
    await repository.add_commitment(
        tenant_context=tenant_context, commitment=commitment
    )
    return commitment


__all__ = ["create_commitment"]
