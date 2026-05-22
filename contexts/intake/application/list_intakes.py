"""list_intakes read use case (D127).

A thin read use case over the IntakeRepository's paginated list
surface. Cursor decoding happens at the transport boundary (CLI /
HTTP); this use case receives a decoded ``IntakeListCursor``.

S44b: accepts an ActorContext, applies the ``requires_authorisation``
decorator, and extracts ``actor.tenant_context`` for the adapter call.
"""

from __future__ import annotations

from contexts.intake.domain.query_filters import (
    IntakeListCursor,
    IntakeListFilters,
)
from contexts.intake.ports.intake_repository import (
    IntakeListPage,
    IntakeRepository,
)
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    INTAKE_RECORD_LIST,
    requires_authorisation,
)

_DEFAULT_PAGE_SIZE: int = 20


@requires_authorisation(INTAKE_RECORD_LIST)
async def list_intakes(
    *,
    repository: IntakeRepository,
    actor: ActorContext,
    filters: IntakeListFilters | None = None,
    cursor: IntakeListCursor | None = None,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> IntakeListPage:
    """Return a paginated page of the tenant's intakes."""
    return await repository.list_for_tenant(
        tenant_context=actor.tenant_context,
        filters=filters,
        cursor=cursor,
        page_size=page_size,
    )


__all__ = ["list_intakes"]
